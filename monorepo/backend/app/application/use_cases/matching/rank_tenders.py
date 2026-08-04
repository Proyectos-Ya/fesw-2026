from typing import Optional
from uuid import UUID

from app.shared.datetime_utils import utc_now_naive

from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.supplier_vector_repository import ISupplierVectorRepository
from app.application.repositories.tender_repository import ITenderRepository, TenderFilters
from app.application.repositories.tender_vector_repository import ITenderVectorRepository
from app.application.repositories.matching_result_repository import IMatchingResultRepository
from app.application.services.reranker_service import IRerankerService
from app.application.services.weighting_service import IWeightingService
from app.application.services.text_builder import TextBuilder
from app.domain.entities.matching_result import MatchingResult
from app.domain.entities.tender import Tender
from app.domain.errors.supplier_errors import SupplierNotFoundForUser, SupplierVectorNotFound
from app.shared.constants import TENDER_STATUSES, ACTIVE_TENDER_STATUSES


class RankTendersUseCase:
    """
    Caso de uso que orquesta el flujo completo de recomendación de licitaciones (tenders)
    para un proveedor, implementando persistencia/caching y re-ranking.
    """

    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        supplier_vector_repo: ISupplierVectorRepository,
        tender_vector_repo: ITenderVectorRepository,
        tender_repo: ITenderRepository,
        reranker_service: IRerankerService,
        weighting_service: IWeightingService,
        matching_result_repo: IMatchingResultRepository,
        model_version: str = "bge-m3-v1",
        vector_search_limit: int = 50,
        reranker_limit: int = 15,
    ) -> None:
        self.supplier_repo = supplier_repo
        self.supplier_vector_repo = supplier_vector_repo
        self.tender_vector_repo = tender_vector_repo
        self.tender_repo = tender_repo
        self.reranker_service = reranker_service
        self.weighting_service = weighting_service
        self.matching_result_repo = matching_result_repo
        self.model_version = model_version
        self.vector_search_limit = vector_search_limit
        self.reranker_limit = reranker_limit
        self.text_builder = TextBuilder()

    async def execute(
        self,
        user_id: UUID,
        force_refresh: bool = False,
    ) -> list[MatchingResult]:
        """
        Ejecuta el flujo de recomendación y retorna el listado de resultados ordenados por score final.
        """
        # 1. Obtener perfil de proveedor asociado al usuario
        supplier = await self.supplier_repo.get_by_user_id(user_id)
        if supplier is None:
            raise SupplierNotFoundForUser(user_id)

        now = utc_now_naive()

        # 2. Si no es forzado, intentar obtener las recomendaciones del cache SQL
        if not force_refresh:
            cached_matches = await self.matching_result_repo.get_by_supplier_id(supplier.id)
            if cached_matches:
                # Hidratar las licitaciones desde SQL
                tender_ids = [m.tender_id for m in cached_matches]
                tenders = await self.tender_repo.get_tenders(TenderFilters(ids=tender_ids))
                tender_dict = {t.id: t for t in tenders}

                valid_results = []
                for m in cached_matches:
                    t = tender_dict.get(m.tender_id)
                    # Descartar licitaciones cerradas o que no estén en estado activa/publicada
                    if t and t.closing_at > now and t.status_code in ACTIVE_TENDER_STATUSES:
                        m.tender = t
                        valid_results.append(m)

                # Si el cache aún contiene recomendaciones válidas, las retornamos ordenadas
                if valid_results:
                    valid_results.sort(key=lambda x: x.final_score, reverse=True)
                    return valid_results

        # 3. Cache vacío, inválido o force_refresh=True: ejecutar el pipeline de recomendación completo
        # 3.1 Obtener vector del proveedor desde Qdrant
        supplier_vector = self.supplier_vector_repo.get_vector(supplier.id)
        if supplier_vector is None:
            raise SupplierVectorNotFound(supplier.id)

        # 3.2 Buscar licitaciones similares en Qdrant (filtrando por estado publicada)
        search_results = await self.tender_vector_repo.search_by_supplier_vector(
            supplier_vector=supplier_vector,
            limit=self.vector_search_limit,
            filters={"status_code": TENDER_STATUSES["PUBLISHED"]},
        )
        if not search_results:
            # Si no hay matches, limpiamos cache anterior y retornamos vacío
            await self.matching_result_repo.delete_by_supplier_id(supplier.id)
            return []

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

        # 3.4 Filtrar closed tenders secundariamente (por fecha de cierre en SQL)
        active_tenders = []
        similarity_scores = {}
        for uid, sim_score in search_results:
            t = tender_dict.get(uid)
            if t and t.closing_at > now and t.status_code in ACTIVE_TENDER_STATUSES:
                active_tenders.append(t)
                similarity_scores[uid] = sim_score

        if not active_tenders:
            await self.matching_result_repo.delete_by_supplier_id(supplier.id)
            return []

        # 3.5 Re-ranking con cross-encoder (ONNX)
        supplier_text = self.text_builder.build_from_supplier(supplier)
        candidates = []
        for t in active_tenders:
            # Construir texto representativo de la licitación
            tender_text = self.text_builder.build_from_tender(tender=t, items=t.items)
            candidates.append((t.id, tender_text))

        # Ejecutar el servicio de re-ranking (retorna tuplas de (tender_id, score))
        reranked_scores = await self.reranker_service.rerank(
            query_text=supplier_text,
            candidates=candidates,
            limit=self.reranker_limit,
        )
        reranked_dict = {uid: score for uid, score in reranked_scores}

        # Filtrar active_tenders para dejar solo los re-rankeados (top M),
        # en tuplas (tender, score_reranker) como exige IWeightingService
        top_candidates = [
            (t, reranked_dict[t.id]) for t in active_tenders if t.id in reranked_dict
        ]

        # 3.6 Ponderación manual (IWeightingService): retorna (tender_id, score_final)
        weighted_results = self.weighting_service.calculate_scores(top_candidates, supplier)

        # 3.7 Construir entidades MatchingResult definitivas
        tender_by_id = {t.id: t for t in active_tenders}
        new_matches = []
        for tender_id, final_score in weighted_results:
            t = tender_by_id[tender_id]
            sim_score = similarity_scores.get(tender_id, 0.0)
            rerank_score = reranked_dict.get(tender_id)

            match_res = MatchingResult(
                supplier_id=supplier.id,
                tender_id=tender_id,
                similarity_score=sim_score,
                reranker_score=rerank_score,
                final_score=final_score,
                model_version=self.model_version,
                tender=t,
            )
            new_matches.append(match_res)

        # Ordenar por final_score descendente
        new_matches.sort(key=lambda x: x.final_score, reverse=True)

        # 3.8 Persistir en la base de datos SQL (caching)
        await self.matching_result_repo.delete_by_supplier_id(supplier.id)
        await self.matching_result_repo.save_bulk(new_matches)

        return new_matches
