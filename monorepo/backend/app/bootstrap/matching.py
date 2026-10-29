"""Providers de matching, búsqueda, detalle de licitaciones y licitaciones guardadas."""

from typing import Annotated

from fastapi import Depends

from app.application.repositories.lexical_tender_repository import (
    ILexicalTenderRepository,
)
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
from app.application.repositories.tender_repository import ITenderRepository
from app.application.repositories.tender_vector_repository import (
    ITenderVectorRepository,
)
from app.application.services.compatibility_formula import (
    CalibrationCoefficients,
    CompatibilityFormula,
)
from app.application.services.compatibility_scorer import CompatibilityScorer
from app.application.services.deep_analysis_service import IDeepAnalysisService
from app.application.services.embedding_service import IEmbeddingService
from app.application.services.reranker_service import IRerankerService
from app.application.use_cases.deep_analysis.get_or_create_deep_analysis import (
    GetOrCreateDeepAnalysisUseCase,
)
from app.application.use_cases.questions.generate_tender_smart_questions_use_case import (
    GenerateTenderSmartQuestionsUseCase,
)
from app.bootstrap.questions import get_generate_tender_smart_questions_use_case
from app.application.use_cases.matching.rank_tenders import RankTendersUseCase
from app.application.use_cases.matching.score_tender_on_demand import (
    ScoreTenderOnDemandUseCase,
)
from app.application.use_cases.matching_shadow import ComputeShadowScoreUseCase
from app.application.use_cases.saved_tenders.list_saved_tenders import (
    ListSavedTendersUseCase,
)
from app.application.use_cases.saved_tenders.save_tender import SaveTenderUseCase
from app.application.use_cases.saved_tenders.unsave_tender import UnsaveTenderUseCase
from app.application.use_cases.tender.get_tender_detail import GetTenderDetailUseCase
from app.application.use_cases.tender.search_tenders import SearchTendersUseCase
from app.bootstrap.repositories import (
    AttachmentExtractionRepoDep,
    MatchingResultRepoDep,
    MatchingShadowRepoDep,
    SavedTenderRepoDep,
    SupplierRepoDep,
    TenderDigestRepoDep,
    TenderRepoDep,
)
from app.bootstrap.services import (
    CompatibilityFormulaDep,
    EmbeddingServiceDep,
    LexicalTenderRepoDep,
    SupplierVectorRepoDep,
    TenderItemVectorRepoDep,
    TenderVectorRepoDep,
    get_deep_analysis_service,
    get_reranker_service,
)
from app.config import settings

# Versión de la fórmula de compatibilidad. Se sube a mano cada vez que cambian los
# coeficientes de `settings.compatibility_*` o las señales que los alimentan: es lo
# que hace que los porcentajes cacheados con la fórmula anterior se recalculen.
COMPATIBILITY_FORMULA_VERSION = "compat-calib-v1"


def compatibility_model_version() -> str:
    """Identifica embeddings y fórmula juntos, para `MatchingResult.model_version`.

    `RankTendersUseCase` compara este valor con el de la caché de
    recomendaciones. Antes era solo el modelo de embeddings, que no cambia
    cuando se recalibra la fórmula: desplegar coeficientes nuevos habría dejado
    a cada usuario viendo los porcentajes viejos hasta su próximo cambio de perfil.
    """
    return f"{settings.embedding_model}+{COMPATIBILITY_FORMULA_VERSION}"


def build_compatibility_formula() -> CompatibilityFormula:
    """Arma la fórmula calibrada con los coeficientes de la configuración."""
    return CompatibilityFormula(
        relevant=CalibrationCoefficients(
            intercept=settings.compatibility_relevant_intercept,
            reranker=settings.compatibility_relevant_reranker,
            best_match=settings.compatibility_relevant_best_match,
            coverage=settings.compatibility_relevant_coverage,
        ),
        exact=CalibrationCoefficients(
            intercept=settings.compatibility_exact_intercept,
            reranker=settings.compatibility_exact_reranker,
            best_match=settings.compatibility_exact_best_match,
            coverage=settings.compatibility_exact_coverage,
        ),
    )


# Constructores compartidos por los providers de la API y por los runners del
# scheduler. Los argumentos son obligatorios y por nombre: si alguien agrega una
# dependencia, todos los que arman el caso de uso tienen que pasarla, en vez de
# quedarse en silencio con el valor por defecto del constructor.


def build_compatibility_scorer(
    *,
    reranker_service: IRerankerService,
    matching_result_repo: IMatchingResultRepository,
    embedding_service: IEmbeddingService,
    item_vector_repo: ITenderItemVectorRepository,
    formula: CompatibilityFormula,
) -> CompatibilityScorer:
    """La fórmula de compatibilidad, compartida por el ranking y el cálculo a pedido."""
    return CompatibilityScorer(
        reranker_service=reranker_service,
        matching_result_repo=matching_result_repo,
        embedding_service=embedding_service,
        item_vector_repo=item_vector_repo,
        formula=formula,
        model_version=compatibility_model_version(),
    )


def build_rank_tenders_use_case(
    *,
    supplier_repo: ISupplierRepository,
    supplier_vector_repo: ISupplierVectorRepository,
    tender_vector_repo: ITenderVectorRepository,
    tender_repo: ITenderRepository,
    scorer: CompatibilityScorer,
    matching_result_repo: IMatchingResultRepository,
    embedding_service: IEmbeddingService,
    item_vector_repo: ITenderItemVectorRepository,
    lexical_tender_repo: ILexicalTenderRepository,
) -> RankTendersUseCase:
    # Con el servicio de embeddings, una empresa sin vector en Qdrant lo recupera
    # en vez de fallar con SupplierVectorNotFound. Embeddings y partidas juntos
    # son el segundo canal de candidatas (keywords contra partidas).
    return RankTendersUseCase(
        supplier_repo=supplier_repo,
        supplier_vector_repo=supplier_vector_repo,
        tender_vector_repo=tender_vector_repo,
        tender_repo=tender_repo,
        scorer=scorer,
        matching_result_repo=matching_result_repo,
        model_version=compatibility_model_version(),
        embedding_service=embedding_service,
        item_vector_repo=item_vector_repo,
        # Tercer canal: BM25 léxico sparse (plan 256).
        lexical_tender_repo=lexical_tender_repo,
        lexical_channel_enabled=settings.matching_lexical_channel_enabled,
        lexical_search_limit=settings.matching_lexical_search_limit,
    )


def get_compatibility_scorer(
    reranker_service: Annotated[IRerankerService, Depends(get_reranker_service)],
    matching_result_repo: MatchingResultRepoDep,
    embedding_service: EmbeddingServiceDep,
    item_vector_repo: TenderItemVectorRepoDep,
    formula: CompatibilityFormulaDep,
) -> CompatibilityScorer:
    return build_compatibility_scorer(
        reranker_service=reranker_service,
        matching_result_repo=matching_result_repo,
        embedding_service=embedding_service,
        item_vector_repo=item_vector_repo,
        formula=formula,
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
    item_vector_repo: TenderItemVectorRepoDep,
    lexical_tender_repo: LexicalTenderRepoDep,
) -> RankTendersUseCase:
    return build_rank_tenders_use_case(
        supplier_repo=supplier_repo,
        supplier_vector_repo=supplier_vector_repo,
        tender_vector_repo=tender_vector_repo,
        tender_repo=tender_repo,
        scorer=scorer,
        matching_result_repo=matching_result_repo,
        embedding_service=embedding_service,
        item_vector_repo=item_vector_repo,
        lexical_tender_repo=lexical_tender_repo,
    )


def get_score_tender_on_demand_use_case(
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
    matching_result_repo: MatchingResultRepoDep,
    scorer: CompatibilityScorerDep,
    digest_repo: TenderDigestRepoDep,
    extraction_repo: AttachmentExtractionRepoDep,
) -> ScoreTenderOnDemandUseCase:
    return ScoreTenderOnDemandUseCase(
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        matching_result_repo=matching_result_repo,
        scorer=scorer,
        digest_repo=digest_repo,
        extraction_repo=extraction_repo,
    )


def get_compute_shadow_score_use_case(
    scorer: CompatibilityScorerDep,
    shadow_repo: MatchingShadowRepoDep,
) -> ComputeShadowScoreUseCase:
    # Plan 233, decisión 9. Ninguna ruta lo usa todavía: ver ADR 0005.
    return ComputeShadowScoreUseCase(scorer=scorer, shadow_repo=shadow_repo, settings=settings)


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
    generate_questions_use_case: Annotated[
        GenerateTenderSmartQuestionsUseCase,
        Depends(get_generate_tender_smart_questions_use_case),
    ],
) -> GetOrCreateDeepAnalysisUseCase:
    return GetOrCreateDeepAnalysisUseCase(
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        matching_result_repo=matching_result_repo,
        deep_analysis_service=deep_analysis_service,
        scorer=scorer,
        generate_questions_use_case=generate_questions_use_case,
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
