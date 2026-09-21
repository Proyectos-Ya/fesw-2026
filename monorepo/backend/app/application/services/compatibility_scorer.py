"""Cálculo de compatibilidad entre un proveedor y una o más licitaciones.

Esta era la parte central de `RankTendersUseCase` (pasos 3.5 a 3.7). Se extrajo
porque ahora hay dos caminos que necesitan el mismo número: el ranking, que
puntúa el top-N y lo refresca solo, y el cálculo a pedido sobre una licitación
que el usuario encontró buscando. Con la fórmula en un solo lugar, cambiar los
pesos no puede dejar a un camino diciendo 72% y al otro 58% para el mismo par.

Que la misma función sirva para 50 candidatas o para 1 no es casualidad ni
suerte: ni el reranker ni la ponderación normalizan contra el lote. El reranker
calibra cada par por separado (Platt scaling) y `FieldWeightingService` puntúa
cada licitación contra el perfil, sin mirar a las demás. El tamaño del lote solo
cambia el costo, no el resultado.
"""

from dataclasses import dataclass
from uuid import UUID

from app.application.repositories.matching_result_repository import (
    IMatchingResultRepository,
)
from app.application.services.reranker_service import IRerankerService
from app.application.services.text_builder import TextBuilder
from app.application.services.weighting_service import IWeightingService
from app.domain.entities.matching_result import MatchingResult
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender
from app.domain.errors.matching_errors import ScoreCalculationError


@dataclass(frozen=True)
class ScoredTender:
    """Puntaje de una licitación para un proveedor."""

    tender_id: UUID
    final_score: float
    reranker_score: float | None


class CompatibilityScorer:
    def __init__(
        self,
        reranker_service: IRerankerService,
        weighting_service: IWeightingService,
        matching_result_repo: IMatchingResultRepository,
        model_version: str = "bge-m3-v1",
    ) -> None:
        self.reranker_service = reranker_service
        self.weighting_service = weighting_service
        self.matching_result_repo = matching_result_repo
        self.model_version = model_version
        self.text_builder = TextBuilder()

    async def score_many(
        self,
        supplier: Supplier,
        tenders: list[Tender],
        limit: int,
    ) -> list[ScoredTender]:
        """Puntúa candidatas y devuelve las `limit` mejores, de mayor a menor.

        El corte lo hace el reranker: la ponderación posterior solo recibe las
        que sobrevivieron, igual que antes de la extracción.
        """
        if not tenders:
            return []

        supplier_text = self.text_builder.build_from_supplier(supplier)
        candidates = [
            (t.id, self.text_builder.build_from_tender(tender=t, items=t.items))
            for t in tenders
        ]

        reranked = await self.reranker_service.rerank(
            query_text=supplier_text,
            candidates=candidates,
            limit=limit,
        )
        reranked_scores = dict(reranked)

        top_candidates = [(t, reranked_scores[t.id]) for t in tenders if t.id in reranked_scores]
        weighted_results = self.weighting_service.calculate_scores(
            top_candidates, supplier
        )

        return [
            ScoredTender(
                tender_id=tender_id,
                final_score=final_score,
                reranker_score=reranked_scores.get(tender_id),
            )
            for tender_id, final_score in weighted_results
        ]

    async def score_and_persist(
        self, supplier: Supplier, tender: Tender
    ) -> MatchingResult:
        """Calcula el puntaje de una licitación suelta y lo guarda como `on_demand`.

        Se persiste, y no solo se devuelve, porque el usuario que lo pidió
        espera encontrarlo después: al volver a la ficha, en sus guardadas o en
        el análisis, sin pagar otra inferencia ni ver un número distinto.
        """
        fila, _ = await self._calcular_y_guardar(supplier, tender)
        return fila

    async def score_pct_and_persist(
        self, supplier: Supplier, tender: Tender
    ) -> float:
        """Lo mismo, pero devuelve el porcentaje (0-100) que el análisis justifica.

        Existe para que quien necesita el número no tenga que leerlo de vuelta
        de una fila donde el puntaje es opcional: acá se acaba de calcular, así
        que es un float y nada más.
        """
        _, porcentaje = await self._calcular_y_guardar(supplier, tender)
        return porcentaje

    async def _calcular_y_guardar(
        self, supplier: Supplier, tender: Tender
    ) -> tuple[MatchingResult, float]:
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
                source="on_demand",
            )
        )
        return fila, resultado.final_score * 100.0
