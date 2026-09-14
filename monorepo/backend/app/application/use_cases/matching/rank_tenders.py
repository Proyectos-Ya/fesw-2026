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
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.repositories.tender_vector_repository import (
    ITenderVectorRepository,
)
from app.application.schemas.tender_schema import TenderFilterCriteria
from app.application.services.compatibility_scorer import CompatibilityScorer
from app.domain.entities.matching_result import MatchingResult
from app.domain.errors.supplier_errors import (
    SupplierNotFoundForUser,
    SupplierVectorNotFound,
)
from app.shared.constants import ACTIVE_TENDER_STATUSES, TENDER_STATUSES
from app.shared.datetime_utils import utc_now_naive
from app.shared.regions import are_regions_matching


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

    async def execute(
        self,
        user_id: UUID,
        force_refresh: bool = False,
        request: ClientConnection | None = None,
    ) -> list[MatchingResult]:
        """
        Ejecuta el flujo de recomendación y retorna el listado de resultados ordenados por score final.
        """
        if request is not None and await request.is_disconnected():
            raise asyncio.CancelledError()

        # 1. Obtener perfil de proveedor asociado al usuario
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
                supplier_changed_time = (
                    supplier.profile_changed_at or supplier.updated_at
                )

                cache_is_stale = False
                if latest_cache_time is not None:
                    # Se invalida una vez por corrida de ingesta, no por licitación:
                    # el cron diario inserta ~4.500 licitaciones durante ~50 min y el
                    # escaneo de alertas pasa cada 5 min, así que comparar contra la
                    # última licitación recalculaba ~10 veces por empresa por noche,
                    # y cada recálculo gasta cupo de Pinecone.
                    last_ingestion_time = (
                        await self.tender_repo.get_latest_ingestion_finished_at()
                    )
                    if last_ingestion_time is not None:
                        # Límite conocido: con corridas del cron ya registradas, una
                        # carga manual (bootstrap_corpus) no refresca la caché hasta
                        # la corrida siguiente, un cambio de perfil o force_refresh.
                        if last_ingestion_time > latest_cache_time:
                            cache_is_stale = True
                    else:
                        # Respaldo sin corridas registradas: el scheduler en proceso y
                        # bootstrap_corpus no escriben en `ingestion_run`. Se invalida
                        # por licitación nueva, con 30 s de gracia para no recalcular
                        # en cada inserción.
                        latest_tender_time = (
                            await self.tender_repo.get_latest_tender_created_at()
                        )
                        cache_age = now - latest_cache_time
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
        if supplier_vector is None:
            raise SupplierVectorNotFound(supplier.id)

        # 3.2 Buscar licitaciones similares en Qdrant (filtrando por estado publicada)
        search_results = await self.tender_vector_repo.search_by_vector(
            vector=supplier_vector,
            limit=self.vector_search_limit,
            criteria=TenderFilterCriteria(status_codes=[TENDER_STATUSES["PUBLISHED"]]),
        )
        if not search_results:
            # Si no hay matches, limpiamos cache anterior y retornamos vacío
            await self.matching_result_repo.delete_ranking_by_supplier_id(supplier.id)
            return []

        if request is not None and await request.is_disconnected():
            raise asyncio.CancelledError()

        # 3.3 Hidratar las licitaciones desde SQL
        tender_ids = [uid for uid, _ in search_results]
        tenders = await self.tender_repo.get_tenders(TenderFilters(ids=tender_ids))
        tender_dict = {t.id: t for t in tenders}

        # 3.3.1 Limpieza de puntos huérfanos: IDs presentes en Qdrant pero sin fila
        # en SQL (p. ej. por reseteos de la BD). Se eliminan del almacén vectorial
        # para que no ocupen cupos del top-N en búsquedas futuras.
        for uid, _ in search_results:
            if uid not in tender_dict:
                await self.tender_vector_repo.delete(uid)

        # 3.4 Filtrar closed tenders secundariamente (por fecha de cierre en SQL y región estricta)
        active_tenders = []
        similarity_scores = {}
        for uid, sim_score in search_results:
            t = tender_dict.get(uid)
            if t and t.closing_at > now and t.status_code in ACTIVE_TENDER_STATUSES:
                # Filtrar estrictamente por región canónica si el proveedor tiene regiones configuradas
                if supplier.regions and not are_regions_matching(
                    t.region, supplier.regions
                ):
                    continue
                active_tenders.append(t)
                similarity_scores[uid] = sim_score

        if not active_tenders:
            await self.matching_result_repo.delete_ranking_by_supplier_id(supplier.id)
            return []

        if request is not None and await request.is_disconnected():
            raise asyncio.CancelledError()

        # 3.5 Re-ranking y ponderación: la misma fórmula que usa el cálculo a
        # pedido de una licitación suelta (CompatibilityScorer).
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
                similarity_score=similarity_scores.get(resultado.tender_id, 0.0),
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
