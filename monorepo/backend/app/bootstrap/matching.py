"""Providers de matching, búsqueda, detalle de licitaciones y licitaciones guardadas."""

from typing import Annotated

from fastapi import Depends

from app.application.services.compatibility_scorer import CompatibilityScorer
from app.application.services.deep_analysis_service import IDeepAnalysisService
from app.application.services.reranker_service import IRerankerService
from app.application.services.weighting_service import IWeightingService
from app.application.use_cases.deep_analysis.get_or_create_deep_analysis import (
    GetOrCreateDeepAnalysisUseCase,
)
from app.application.use_cases.matching.rank_tenders import RankTendersUseCase
from app.application.use_cases.matching.score_tender_on_demand import (
    ScoreTenderOnDemandUseCase,
)
from app.application.use_cases.saved_tenders.list_saved_tenders import (
    ListSavedTendersUseCase,
)
from app.application.use_cases.saved_tenders.save_tender import SaveTenderUseCase
from app.application.use_cases.saved_tenders.unsave_tender import UnsaveTenderUseCase
from app.application.use_cases.tender.get_tender_detail import GetTenderDetailUseCase
from app.application.use_cases.tender.search_tenders import SearchTendersUseCase
from app.bootstrap.repositories import (
    MatchingResultRepoDep,
    SavedTenderRepoDep,
    SupplierRepoDep,
    TenderRepoDep,
)
from app.bootstrap.services import (
    EmbeddingServiceDep,
    SupplierVectorRepoDep,
    TenderVectorRepoDep,
    get_deep_analysis_service,
    get_reranker_service,
    get_weighting_service,
)
from app.config import settings


def get_compatibility_scorer(
    reranker_service: Annotated[IRerankerService, Depends(get_reranker_service)],
    weighting_service: Annotated[IWeightingService, Depends(get_weighting_service)],
    matching_result_repo: MatchingResultRepoDep,
) -> CompatibilityScorer:
    """La fórmula de compatibilidad, compartida por el ranking y el cálculo a pedido."""
    return CompatibilityScorer(
        reranker_service=reranker_service,
        weighting_service=weighting_service,
        matching_result_repo=matching_result_repo,
        model_version=settings.embedding_model,
    )


CompatibilityScorerDep = Annotated[CompatibilityScorer, Depends(get_compatibility_scorer)]


def get_rank_tenders_use_case(
    supplier_repo: SupplierRepoDep,
    supplier_vector_repo: SupplierVectorRepoDep,
    tender_vector_repo: TenderVectorRepoDep,
    tender_repo: TenderRepoDep,
    scorer: CompatibilityScorerDep,
    matching_result_repo: MatchingResultRepoDep,
    embedding_service: EmbeddingServiceDep,
) -> RankTendersUseCase:
    return RankTendersUseCase(
        supplier_repo=supplier_repo,
        supplier_vector_repo=supplier_vector_repo,
        tender_vector_repo=tender_vector_repo,
        tender_repo=tender_repo,
        scorer=scorer,
        matching_result_repo=matching_result_repo,
        model_version=settings.embedding_model,
        embedding_service=embedding_service,
    )


def get_score_tender_on_demand_use_case(
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
    matching_result_repo: MatchingResultRepoDep,
    scorer: CompatibilityScorerDep,
) -> ScoreTenderOnDemandUseCase:
    return ScoreTenderOnDemandUseCase(
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        matching_result_repo=matching_result_repo,
        scorer=scorer,
    )


def get_search_tenders_use_case(
    supplier_repo: SupplierRepoDep,
    supplier_vector_repo: SupplierVectorRepoDep,
    tender_vector_repo: TenderVectorRepoDep,
    tender_repo: TenderRepoDep,
    embedding_service: EmbeddingServiceDep,
) -> SearchTendersUseCase:
    return SearchTendersUseCase(
        supplier_repo=supplier_repo,
        supplier_vector_repo=supplier_vector_repo,
        tender_vector_repo=tender_vector_repo,
        tender_repo=tender_repo,
        embedding_service=embedding_service,
    )


def get_tender_detail_use_case(
    tender_repo: TenderRepoDep,
    supplier_repo: SupplierRepoDep,
    matching_result_repo: MatchingResultRepoDep,
) -> GetTenderDetailUseCase:
    return GetTenderDetailUseCase(
        tender_repo=tender_repo,
        supplier_repo=supplier_repo,
        matching_result_repo=matching_result_repo,
    )


def get_get_or_create_deep_analysis_use_case(
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
    matching_result_repo: MatchingResultRepoDep,
    deep_analysis_service: Annotated[
        IDeepAnalysisService, Depends(get_deep_analysis_service)
    ],
    scorer: CompatibilityScorerDep,
) -> GetOrCreateDeepAnalysisUseCase:
    return GetOrCreateDeepAnalysisUseCase(
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        matching_result_repo=matching_result_repo,
        deep_analysis_service=deep_analysis_service,
        scorer=scorer,
    )


def get_list_saved_tenders_use_case(
    saved_tender_repo: SavedTenderRepoDep,
    tender_repo: TenderRepoDep,
    supplier_repo: SupplierRepoDep,
    matching_result_repo: MatchingResultRepoDep,
) -> ListSavedTendersUseCase:
    return ListSavedTendersUseCase(
        saved_tender_repo=saved_tender_repo,
        tender_repo=tender_repo,
        supplier_repo=supplier_repo,
        matching_result_repo=matching_result_repo,
    )


def get_save_tender_use_case(
    saved_tender_repo: SavedTenderRepoDep,
    tender_repo: TenderRepoDep,
) -> SaveTenderUseCase:
    return SaveTenderUseCase(saved_tender_repo=saved_tender_repo, tender_repo=tender_repo)


def get_unsave_tender_use_case(saved_tender_repo: SavedTenderRepoDep) -> UnsaveTenderUseCase:
    return UnsaveTenderUseCase(saved_tender_repo=saved_tender_repo)
