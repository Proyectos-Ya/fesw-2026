"""Cálculo de compatibilidad entre un proveedor y una o más licitaciones.

Esta era la parte central de `RankTendersUseCase` (pasos 3.5 a 3.7). Se extrajo
porque ahora hay dos caminos que necesitan el mismo número: el ranking, que
puntúa el top-N y lo refresca solo, y el cálculo a pedido sobre una licitación
que el usuario encontró buscando. Con la fórmula en un solo lugar, cambiar los
coeficientes no puede dejar a un camino diciendo 72% y al otro 58% para el mismo
par.

La fórmula
----------
El porcentaje deja de ser la suma ponderada de `FieldWeightingService`
(0,5·reranker + 0,25·rubro + 0,25·keywords) y pasa a una regresión logística
calibrada (`CompatibilityFormula`) sobre tres señales:

- **R** — el reranker puntuando el par con una consulta corta
  ("Rubro: … Productos: …", `TextBuilder.build_reranker_query`) contra el texto de
  la licitación.
- **B** — el mejor calce entre una keyword del proveedor y una partida de la
  licitación (coseno máximo de la matriz keyword × partida).
- **C** — la cobertura: qué parte de lo que pide la licitación cubre el
  proveedor (promedio, sobre partidas, del mejor coseno de cada una).

Por qué: sobre 1.146 pares juzgados, la fórmula anterior tenía AUC 0,58 para
separar licitaciones relevantes de las que no; esta llega a 0,75 con validación
cruzada por proveedor. Además, el bono léxico casi nunca se activaba, así que el
máximo real era ~50 % del reranker y casi nada llegaba al 70 % que exige el
selector verde. Detalle en `spikes/dataset_compra_agil/calibrar_multivector.py` y
`spikes/spike-2/README.md`, sección 7.

Que la misma función sirva para 50 candidatas o para 1 no es casualidad ni
suerte: nada se normaliza contra el lote. El reranker puntúa cada par por
separado (ya no en un batch, donde la cuantización dinámica del modelo INT8 hacía
depender el logit de las demás candidatas), y B, C y la fórmula miran solo a esa
licitación contra el perfil. El tamaño del lote solo cambia el costo, no el
resultado.
"""

from dataclasses import dataclass
from uuid import UUID

from app.application.repositories.matching_result_repository import (
    IMatchingResultRepository,
)
from app.application.repositories.tender_item_vector_repository import (
    ITenderItemVectorRepository,
)
from app.application.services.compatibility_formula import (
    CompatibilityFormula,
    item_match_signals,
)
from app.application.services.embedding_service import IEmbeddingService
from app.application.services.reranker_service import IRerankerService
from app.application.services.text_builder import TextBuilder
from app.domain.entities.matching_result import MatchingResult, MatchingSource
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender
from app.domain.errors.matching_errors import ScoreCalculationError


@dataclass(frozen=True)
class ScoredTender:
    """Puntaje de una licitación para un proveedor."""

    tender_id: UUID
    final_score: float
    reranker_score: float | None


@dataclass(frozen=True)
class CompatibilitySignals:
    """Señales R, B, C y puntaje final (plan 233, decisión 9)."""

    reranker_score: float
    best_match: float
    coverage: float
    final_score: float


class CompatibilityScorer:
    def __init__(
        self,
        reranker_service: IRerankerService,
        matching_result_repo: IMatchingResultRepository,
        embedding_service: IEmbeddingService,
        item_vector_repo: ITenderItemVectorRepository,
        formula: CompatibilityFormula,
        model_version: str,
    ) -> None:
        self.reranker_service = reranker_service
        self.matching_result_repo = matching_result_repo
        self.embedding_service = embedding_service
        self.item_vector_repo = item_vector_repo
        self.formula = formula
        # Identifica embeddings y fórmula a la vez: `RankTendersUseCase` descarta
        # como vencido el ranking cacheado con otra versión.
        self.model_version = model_version
        self.text_builder = TextBuilder()

    async def score_many(
        self,
        supplier: Supplier,
        tenders: list[Tender],
        limit: int,
    ) -> list[ScoredTender]:
        """Puntúa candidatas y devuelve las `limit` mejores, de mayor a menor.

        Se rerankean **todas**: hace falta R de cada una para combinarlo con B y
        C, y recién con el puntaje final se recorta. Antes el corte lo hacía el
        reranker, porque lo que venía después era solo una ponderación de las
        que sobrevivían.
        """
        if not tenders:
            return []

        candidates = [
            (t.id, self.text_builder.build_from_tender(tender=t, items=t.items))
            for t in tenders
        ]
        reranked = await self.reranker_service.rerank(
            query_text=self.text_builder.build_reranker_query(supplier),
            candidates=candidates,
            limit=len(candidates),
        )
        reranker_scores = dict(reranked)

        # Una candidata que el reranker no devolvió no tiene R, y sin R no hay
        # puntaje que calcular: se omite en vez de inventarle uno.
        scorable = [t for t in tenders if t.id in reranker_scores]
        if not scorable:
            return []

        keyword_vectors = await self._keyword_vectors(supplier)
        item_vectors = await self._item_vectors(scorable)

        scored: list[ScoredTender] = []
        for tender in scorable:
            reranker_score = reranker_scores[tender.id]
            best_match, coverage = item_match_signals(
                keyword_vectors, item_vectors[tender.id]
            )
            scored.append(
                ScoredTender(
                    tender_id=tender.id,
                    final_score=self.formula.score(
                        reranker_score, best_match, coverage
                    ),
                    reranker_score=reranker_score,
                )
            )

        scored.sort(key=lambda s: s.final_score, reverse=True)
        return scored[:limit]

    async def signals(
        self,
        supplier: Supplier,
        tender: Tender,
        digest: object | None = None,
        variant: str = "att-text-v1",
    ) -> CompatibilitySignals | None:
        """Calcula las señales R, B, C y el puntaje final (plan 233, decisión 9).

        - Sin digest: idéntico a `score_many`.
        - Con digest en 'att-text-v1': enriquece la descripción con anexos (tope 512 tokens).
        - Con digest en 'att-items-v1': cruza contra pseudo-partidas de anexos en lugar de tender.items.
        """
        # 1. Candidato de texto para el reranker
        if digest is not None:
            candidate_text = self.text_builder.build_from_tender_with_digest(
                tender=tender, items=tender.items, digest=digest, max_tokens=512
            )
        else:
            candidate_text = self.text_builder.build_from_tender(
                tender=tender, items=tender.items
            )

        query_text = self.text_builder.build_reranker_query(supplier)
        reranked = await self.reranker_service.rerank(
            query_text=query_text,
            candidates=[(tender.id, candidate_text)],
            limit=1,
        )
        if not reranked:
            return None

        reranker_score = reranked[0][1]
        keyword_vectors = await self._keyword_vectors(supplier)

        # 2. Vectores de partidas
        if variant == "att-items-v1" and digest is not None:
            data = getattr(digest, "data", None)
            digest_items = getattr(data, "items", []) if data else []
            if digest_items:
                item_texts = [
                    f"{item.descripcion}: {item.unidad or ''}".strip()
                    for item in digest_items
                    if getattr(item, "descripcion", None)
                ]
                item_vectors = await self.embedding_service.embed(item_texts)
            else:
                item_vectors = (await self._item_vectors([tender]))[tender.id]
        else:
            item_vectors = (await self._item_vectors([tender]))[tender.id]

        best_match, coverage = item_match_signals(keyword_vectors, item_vectors)
        final_score = self.formula.score(reranker_score, best_match, coverage)

        return CompatibilitySignals(
            reranker_score=reranker_score,
            best_match=best_match,
            coverage=coverage,
            final_score=final_score,
        )

    async def _keyword_vectors(self, supplier: Supplier) -> list[list[float]]:
        """Un vector por keyword del proveedor, en una sola llamada al modelo.

        Qué textos se embeben (y qué pasa con un proveedor sin keywords) lo decide
        `TextBuilder.build_keyword_texts`, que comparte con la búsqueda por
        partidas del ranking.
        """
        return await self.embedding_service.embed(
            self.text_builder.build_keyword_texts(supplier)
        )

    async def _item_vectors(
        self, tenders: list[Tender]
    ) -> dict[UUID, list[list[float]]]:
        """Vectores de partidas de cada licitación: guardados, o embebidos al vuelo.

        Las licitaciones que la ingesta o el backfill ya indexaron se leen tal
        cual. Las que faltan (aún no reindexadas) se embeben en **una** llamada
        para todas juntas, no una por licitación.

        Lo embebido al vuelo no se guarda. Este es un camino de lectura: lo
        invocan `GET /tenders/recommended` y el cálculo a pedido, y escribir
        desde acá haría que dos peticiones simultáneas reemplacen el mismo punto
        en Qdrant y que una lectura pague escrituras. Los vectores los llena la
        ingesta al crear o cambiar una licitación, y
        `scripts/backfill_tender_item_vectors.py` para las que ya existían.
        """
        vectors = dict(await self.item_vector_repo.get_many([t.id for t in tenders]))

        missing = [t for t in tenders if t.id not in vectors]
        if missing:
            texts_by_tender = [self._item_texts(t) for t in missing]
            embedded = await self.embedding_service.embed(
                [text for texts in texts_by_tender for text in texts]
            )
            offset = 0
            for tender, texts in zip(missing, texts_by_tender, strict=True):
                vectors[tender.id] = embedded[offset : offset + len(texts)]
                offset += len(texts)

        return vectors

    def _item_texts(self, tender: Tender) -> list[str]:
        """Textos a embeber de una licitación que no tiene vectores guardados.

        Sus partidas, y si no tiene (o ninguna trae nombre), el nombre y la
        descripción de la licitación: el calce contra algo es mejor que ninguno.
        """
        return self.text_builder.build_item_texts(tender.items) or [
            f"{tender.name}. {tender.description or ''}"
        ]

    async def score_and_persist(
        self,
        supplier: Supplier,
        tender: Tender,
        digest: object | None = None,
        source: MatchingSource = "on_demand",
    ) -> MatchingResult:
        """Calcula el puntaje de una licitación suelta y lo guarda como `on_demand` (o preserva `source`).

        Se persiste, y no solo se devuelve, porque el usuario que lo pidió
        espera encontrarlo después: al volver a la ficha, en sus guardadas o en
        el análisis, sin pagar otra inferencia ni ver un número distinto.
        """
        fila, _ = await self._calcular_y_guardar(
            supplier, tender, digest=digest, source=source
        )
        return fila

    async def score_pct_and_persist(
        self,
        supplier: Supplier,
        tender: Tender,
        digest: object | None = None,
        source: MatchingSource = "on_demand",
    ) -> float:
        """Lo mismo, pero devuelve el porcentaje (0-100) que el análisis justifica.

        Existe para que quien necesita el número no tenga que leerlo de vuelta
        de una fila donde el puntaje es opcional: acá se acaba de calcular, así
        que es un float y nada más.
        """
        _, porcentaje = await self._calcular_y_guardar(
            supplier, tender, digest=digest, source=source
        )
        return porcentaje

    async def _calcular_y_guardar(
        self,
        supplier: Supplier,
        tender: Tender,
        digest: object | None = None,
        source: MatchingSource = "on_demand",
    ) -> tuple[MatchingResult, float]:
        if digest is not None:
            sig = await self.signals(supplier, tender, digest=digest)
            if sig is None:
                raise ScoreCalculationError(str(supplier.id), str(tender.id))

            fila = await self.matching_result_repo.save_on_demand(
                MatchingResult(
                    supplier_id=supplier.id,
                    tender_id=tender.id,
                    similarity_score=None,
                    reranker_score=sig.reranker_score,
                    final_score=sig.final_score,
                    model_version=self.model_version,
                    source=source,
                )
            )
            return fila, sig.final_score * 100.0

        scored = await self.score_many(supplier, [tender], limit=1)
        if not scored:
            raise ScoreCalculationError(str(supplier.id), str(tender.id))

        resultado = scored[0]
        fila = await self.matching_result_repo.save_on_demand(
            MatchingResult(
                supplier_id=supplier.id,
                tender_id=tender.id,
                similarity_score=None,
                reranker_score=resultado.reranker_score,
                final_score=resultado.final_score,
                model_version=self.model_version,
                source=source,
            )
        )
        return fila, resultado.final_score * 100.0
