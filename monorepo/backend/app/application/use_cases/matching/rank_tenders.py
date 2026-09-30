import asyncio
from datetime import timedelta
from typing import Protocol
from uuid import UUID

from app.application.repositories.matching_result_repository import (
    IMatchingResultRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.supplier_vector_repository import (
    ISupplierVectorRepository,
)
from app.application.repositories.tender_item_vector_repository import (
    ITenderItemVectorRepository,
)
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.repositories.tender_vector_repository import (
    ITenderVectorRepository,
)
from app.application.schemas.tender_schema import TenderFilterCriteria
from app.application.services.compatibility_scorer import CompatibilityScorer
from app.application.services.embedding_service import IEmbeddingService
from app.application.services.text_builder import TextBuilder
from app.application.use_cases.supplier.create_supplier import _build_supplier_text
from app.domain.entities.matching_result import MatchingResult
from app.domain.entities.supplier import Supplier
from app.domain.errors.supplier_errors import (
    SupplierNotFoundForUser,
    SupplierVectorNotFound,
)
from app.shared.constants import ACTIVE_TENDER_STATUSES, TENDER_STATUSES
from app.shared.datetime_utils import utc_now_naive
from app.shared.regions import are_regions_matching, normalize_region_name


class ClientConnection(Protocol):
    """Lo único que este caso de uso necesita saber del cliente HTTP.

    Se declara como Protocol en vez de recibir un `fastapi.Request` para no
    arrastrar el framework hasta la capa de aplicación: el pipeline completo es
    caro y conviene abortarlo si el usuario ya cerró la pestaña, pero eso no
    justifica invertir la dirección de dependencias.
    """

    async def is_disconnected(self) -> bool: ...


class RankTendersUseCase:
    """
    Caso de uso que orquesta el flujo completo de recomendación de licitaciones (tenders)
    para un proveedor, implementando persistencia/caching, re-ranking y filtrado estricto por región.

    Las candidatas salen de dos búsquedas vectoriales que se unen antes de
    puntuar: el vector del perfil completo contra las licitaciones y, si hay
    `item_vector_repo`, las keywords del proveedor contra las partidas (MaxSim).
    La segunda recupera licitaciones cuya partida calza con una keyword puntual
    pero cuyo texto global no se parece al perfil. Ambas van filtradas por estado
    y región **dentro** de Qdrant: filtrar después el top-N descartaba casi todo
    para un proveedor de una región chica.
    """

    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        supplier_vector_repo: ISupplierVectorRepository,
        tender_vector_repo: ITenderVectorRepository,
        tender_repo: ITenderRepository,
        scorer: CompatibilityScorer,
        matching_result_repo: IMatchingResultRepository,
        model_version: str = "bge-m3-v1",
        vector_search_limit: int = 50,
        reranker_limit: int = 12,
        embedding_service: IEmbeddingService | None = None,
        item_vector_repo: ITenderItemVectorRepository | None = None,
        item_search_limit: int = 30,
    ) -> None:
        self.supplier_repo = supplier_repo
        self.supplier_vector_repo = supplier_vector_repo
        self.tender_vector_repo = tender_vector_repo
        self.tender_repo = tender_repo
        self.scorer = scorer
        self.matching_result_repo = matching_result_repo
        self.model_version = model_version
        self.vector_search_limit = vector_search_limit
        self.reranker_limit = reranker_limit
        self.embedding_service = embedding_service
        # Sin repo de partidas (o sin cómo embeber las keywords) no hay segundo
        # canal y el ranking parte solo del vector del perfil, como antes.
        self.item_vector_repo = item_vector_repo
        self.item_search_limit = item_search_limit
        self.text_builder = TextBuilder()

    async def execute(
        self,
        user_id: UUID,
        supplier_id: UUID | None = None,
        force_refresh: bool = False,
        request: ClientConnection | None = None,
    ) -> list[MatchingResult]:
        """
        Ejecuta el flujo de recomendación y retorna el listado de resultados ordenados por score final.
        """
        if request is not None and await request.is_disconnected():
            raise asyncio.CancelledError()

        # 1. Obtener perfil de proveedor asociado al espacio de trabajo activo o al usuario
        supplier = None
        if supplier_id is not None:
            supplier = await self.supplier_repo.get_by_id(supplier_id)
        if supplier is None:
            supplier = await self.supplier_repo.get_by_user_id(user_id)

        if supplier is None:
            raise SupplierNotFoundForUser(user_id)


        now = utc_now_naive()

        # 2. Si no es forzado, intentar obtener las recomendaciones del cache SQL
        if not force_refresh:
            cached_matches = await self.matching_result_repo.get_ranking_by_supplier_id(
                supplier.id
            )
            if cached_matches:
                latest_cache_time = max(
                    (m.calculated_at for m in cached_matches), default=None
                )
                latest_tender_time = (
                    await self.tender_repo.get_latest_tender_created_at()
                )
                supplier_changed_time = (
                    supplier.profile_changed_at or supplier.updated_at
                )

                cache_is_stale = False
                if latest_cache_time is not None:
                    cache_age = now - latest_cache_time
                    # Para no saturar el servidor con re-rankings en cada ingesta continua de 2s,
                    # solo invalidamos por nuevas licitaciones si la caché tiene más de 30 segundos de antigüedad.
                    if (
                        latest_tender_time
                        and latest_tender_time > latest_cache_time
                        and cache_age > timedelta(seconds=30)
                    ):
                        cache_is_stale = True
                    # Si el proveedor actualizó su perfil, invalidamos de inmediato
                    if (
                        supplier_changed_time
                        and supplier_changed_time > latest_cache_time
                    ):
                        cache_is_stale = True

                # Si alguna fila se calculó con otra versión de embeddings o de
                # fórmula, sus porcentajes ya no son los que hoy daría el
                # pipeline. Sin esta comparación, tras un despliegue el usuario
                # seguiría viendo los números viejos hasta que llegara una
                # licitación nueva o cambiara su perfil. Basta una fila distinta
                # para recalcular todo: mezclar versiones en una misma lista
                # dejaría porcentajes que no son comparables entre sí.
                if any(m.model_version != self.model_version for m in cached_matches):
                    cache_is_stale = True

                if not cache_is_stale:
                    # Hidratar las licitaciones desde SQL
                    tender_ids = [m.tender_id for m in cached_matches]
                    tenders = await self.tender_repo.get_tenders(
                        TenderFilters(ids=tender_ids)
                    )
                    tender_dict = {t.id: t for t in tenders}

                    valid_results = []
                    for m in cached_matches:
                        t = tender_dict.get(m.tender_id)
                        # Descartar licitaciones cerradas o que no estén en estado activa/publicada
                        if (
                            t
                            and t.closing_at > now
                            and t.status_code in ACTIVE_TENDER_STATUSES
                        ):
                            # Filtrar estrictamente por región si el proveedor tiene regiones configuradas
                            if supplier.regions and not are_regions_matching(
                                t.region, supplier.regions
                            ):
                                continue
                            m.tender = t
                            valid_results.append(m)

                    # Si el cache aún contiene recomendaciones válidas y frescas, las retornamos ordenadas
                    if valid_results:
                        valid_results.sort(key=lambda x: x.final_score, reverse=True)
                        return valid_results

        if request is not None and await request.is_disconnected():
            raise asyncio.CancelledError()

        # 3. Cache vacío, inválido o force_refresh=True: ejecutar el pipeline de recomendación completo
        # 3.1 Obtener vector del proveedor desde Qdrant
        supplier_vector = await self.supplier_vector_repo.get_vector(supplier.id)
        if supplier_vector is None and self.embedding_service is not None:
            text = _build_supplier_text(supplier)
            vectors = await self.embedding_service.embed([text])
            if vectors:
                supplier_vector = vectors[0]
                await self.supplier_vector_repo.upsert(supplier.id, supplier_vector)
        if supplier_vector is None:
            raise SupplierVectorNotFound(supplier.id)

        # 3.2 Buscar candidatas en Qdrant. El estado publicada y las regiones del
        # proveedor viajan como criterio de la búsqueda, no se aplican al top-N ya
        # devuelto: con la región después, un proveedor del Biobío recibía 6
        # candidatas de 50 habiendo 134 en su región.
        criteria = TenderFilterCriteria(
            status_codes=[TENDER_STATUSES["PUBLISHED"]],
            region_ids=self._region_ids(supplier),
        )
        # 3.2.1 Canal por perfil: el vector del perfil completo contra las licitaciones.
        profile_results = await self.tender_vector_repo.search_by_vector(
            vector=supplier_vector,
            limit=self.vector_search_limit,
            criteria=criteria,
        )
        # 3.2.2 Canal por partidas: cada keyword contra los vectores de partidas.
        keyword_results = await self._search_by_keywords(supplier, criteria)

        # Unión sin duplicados. Si una licitación la trajeron los dos canales
        # conserva la similitud de perfil; la que solo vino por keywords no tiene
        # ninguna (ver 3.6).
        similarity_scores: dict[UUID, float] = dict(profile_results)
        keyword_ids = list(dict.fromkeys(uid for uid, _ in keyword_results))
        candidate_ids = list(similarity_scores)
        candidate_ids += [uid for uid in keyword_ids if uid not in similarity_scores]
        if not candidate_ids:
            # Si no hay matches, limpiamos cache anterior y retornamos vacío
            await self.matching_result_repo.delete_ranking_by_supplier_id(supplier.id)
            return []

        if request is not None and await request.is_disconnected():
            raise asyncio.CancelledError()

        # 3.3 Hidratar las licitaciones desde SQL
        tenders = await self.tender_repo.get_tenders(TenderFilters(ids=candidate_ids))
        tender_dict = {t.id: t for t in tenders}

        # 3.3.1 Limpieza de puntos huérfanos: IDs presentes en Qdrant pero sin fila
        # en SQL (p. ej. por reseteos de la BD). Se eliminan del almacén vectorial
        # de donde vinieron para que no ocupen cupos del top-N en búsquedas futuras:
        # del de licitaciones los del canal por perfil y del de partidas los del
        # canal por keywords (los que trajeron ambos, de los dos).
        for uid in similarity_scores:
            if uid not in tender_dict:
                await self.tender_vector_repo.delete(uid)
        if self.item_vector_repo is not None:
            for uid in keyword_ids:
                if uid not in tender_dict:
                    await self.item_vector_repo.delete(uid)

        # 3.4 Filtrar closed tenders secundariamente (por fecha de cierre en SQL y región estricta)
        active_tenders = []
        for uid in candidate_ids:
            t = tender_dict.get(uid)
            if t and t.closing_at > now and t.status_code in ACTIVE_TENDER_STATUSES:
                # Red de seguridad: la región ya filtró dentro de Qdrant, pero su
                # payload `region_id` puede estar desactualizado (p. ej. se
                # corrigió la región en SQL y no se re-sincronizó). La fuente de
                # verdad es SQL, así que se vuelve a filtrar estrictamente por
                # región canónica si el proveedor tiene regiones configuradas.
                if supplier.regions and not are_regions_matching(
                    t.region, supplier.regions
                ):
                    continue
                active_tenders.append(t)

        if not active_tenders:
            await self.matching_result_repo.delete_ranking_by_supplier_id(supplier.id)
            return []

        if request is not None and await request.is_disconnected():
            raise asyncio.CancelledError()

        # 3.5 Puntaje (reranker + calce de keywords con las partidas): la misma
        # fórmula que usa el cálculo a pedido de una licitación suelta
        # (CompatibilityScorer). Puntúa todas las candidatas y recién ahí recorta.
        scored = await self.scorer.score_many(
            supplier, active_tenders, limit=self.reranker_limit
        )

        # 3.6 Construir entidades MatchingResult definitivas
        tender_by_id = {t.id: t for t in active_tenders}
        new_matches = []
        for resultado in scored:
            t = tender_by_id[resultado.tender_id]

            match_res = MatchingResult(
                supplier_id=supplier.id,
                tender_id=resultado.tender_id,
                # Nula para lo que solo trajo el canal de keywords: su puntaje
                # MaxSim no está en la escala de la similitud del perfil, y un
                # 0.0 diría "sin parecido" de algo que sí calzó.
                similarity_score=similarity_scores.get(resultado.tender_id),
                reranker_score=resultado.reranker_score,
                final_score=resultado.final_score,
                model_version=self.model_version,
                source="ranking",
                tender=t,
            )
            new_matches.append(match_res)

        # Ordenar por final_score descendente
        new_matches.sort(key=lambda x: x.final_score, reverse=True)

        if request is not None and await request.is_disconnected():
            raise asyncio.CancelledError()

        # 3.7 Persistir en la base de datos SQL (caching)
        await self.matching_result_repo.delete_ranking_by_supplier_id(supplier.id)
        # Una licitación que el usuario ya se había calculado a pedido puede
        # entrar al top: su fila vieja tiene que salir antes de insertar la
        # nueva, o choca con la restricción única del par.
        await self.matching_result_repo.delete_by_supplier_and_tender_ids(
            supplier.id, [m.tender_id for m in new_matches]
        )
        await self.matching_result_repo.save_bulk(new_matches)

        return new_matches

    @staticmethod
    def _region_ids(supplier: Supplier) -> list[int] | None:
        """Ids de las regiones del proveedor, para acotar la búsqueda vectorial.

        El perfil guarda nombres ("Región del Biobío", "Metropolitana"...) y el
        payload de Qdrant indexa el id, así que se traducen con
        `normalize_region_name`. Los que no se reconocen se omiten; si no queda
        ninguno —o el proveedor no declaró regiones— devuelve `None` y no se
        filtra por región, como antes.
        """
        region_ids: list[int] = []
        for name in supplier.regions or []:
            region_id = normalize_region_name(name)
            if region_id is not None and region_id not in region_ids:
                region_ids.append(region_id)
        return region_ids or None

    async def _search_by_keywords(
        self, supplier: Supplier, criteria: TenderFilterCriteria
    ) -> list[tuple[UUID, float]]:
        """Segundo canal de candidatas: las keywords contra los vectores de partidas.

        Devuelve `(tender_id, MaxSim)` de mayor a menor, o nada si no hay repo de
        partidas o servicio de embeddings con que armar los vectores. Usa los
        mismos textos que el scorer (`TextBuilder.build_keyword_texts`).
        """
        if self.item_vector_repo is None or self.embedding_service is None:
            return []
        keyword_vectors = await self.embedding_service.embed(
            self.text_builder.build_keyword_texts(supplier)
        )
        if not keyword_vectors:
            return []
        return await self.item_vector_repo.search_by_keywords(
            keyword_vectors, limit=self.item_search_limit, criteria=criteria
        )
