import asyncio
import logging
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.attachment_extraction_repository import (
    IAttachmentExtractionRepository,
)
from app.application.repositories.attachment_file_repository import (
    IAttachmentFileRepository,
)
from app.application.repositories.attachment_processing_job_repository import (
    IAttachmentProcessingJobRepository,
)
from app.application.repositories.attachment_processing_status_reader import (
    IAttachmentProcessingStatusReader,
)
from app.application.repositories.gemini_usage_repository import (
    IGeminiUsageRepository,
)
from app.application.repositories.tender_digest_repository import (
    ITenderDigestRepository,
)
from app.application.services.attachment_processing_notifier import (
    IAttachmentProcessingNotifier,
)
from app.application.services.enqueue_extraction_listener import (
    EnqueueExtractionOnStored,
)
from app.application.use_cases.attachment_processing.build_tender_digest import (
    BuildTenderDigestUseCase,
)
from app.application.use_cases.attachment_processing.extract_attachment import (
    ExtractAttachmentUseCase,
)
from app.application.use_cases.attachment_processing.get_tender_digest import (
    GetTenderDigestUseCase,
)
from app.application.use_cases.attachment_processing.process_next_job import (
    ProcessNextAttachmentJobUseCase,
)
from app.application.use_cases.attachment_processing.sweep import (
    SweepAttachmentProcessingUseCase,
    SweepResult,
)
from app.application.repositories.calendar_repository import (
    ICalendarConnectionRepository,
)
from app.application.repositories.matching_result_repository import (
    IMatchingResultRepository,
)
from app.application.repositories.notification_repository import (
    INotificationDeliveryRepository,
    INotificationPreferenceRepository,
    INotificationRepository,
)
from app.application.repositories.question_repository import IQuestionRepository
from app.application.repositories.saved_tender_repository import ISavedTenderRepository
from app.application.repositories.supplier_invitation_repository import (
    ISupplierInvitationRepository,
)
from app.application.repositories.supplier_member_repository import (
    ISupplierMemberRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.supplier_vector_repository import (
    ISupplierVectorRepository,
)
from app.application.repositories.tender_attachment_repository import (
    ITenderAttachmentRepository,
)
from app.application.repositories.tender_chat_repository import (
    ITenderChatRepository,
)
from app.application.repositories.tender_item_vector_repository import (
    ITenderItemVectorRepository,
)
from app.application.repositories.tender_repository import ITenderRepository
from app.application.repositories.tender_vector_repository import (
    ITenderVectorRepository,
)
from app.application.repositories.user_repository import IUserRepository
from app.application.services.attachment_deleted_listener import (
    CompositeAttachmentDeletedListener,
    IAttachmentDeletedListener,
)
from app.application.services.attachment_storage import IAttachmentStorage
from app.application.services.attachment_stored_listener import (
    CompositeAttachmentStoredListener,
    IAttachmentStoredListener,
)
from app.application.services.attachment_visibility_listener import (
    IAttachmentVisibilityListener,
    NoopAttachmentVisibilityListener,
)
from app.application.services.calendar_provider_client import (
    CalendarProviders,
    ICalendarProviderClient,
)
from app.application.services.company_lookup_service import ICompanyLookupService
from app.application.services.compatibility_formula import (
    CalibrationCoefficients,
    CompatibilityFormula,
)
from app.application.services.compatibility_scorer import CompatibilityScorer
from app.application.services.deep_analysis_service import IDeepAnalysisService
from app.application.services.document_validator_service import (
    IDocumentValidatorService,
)
from app.application.services.document_analysis_quotation_service import (
    IDocumentAnalysisAndQuotationService,
)
from app.application.services.email_service import IEmailService
from app.application.services.embedding_service import IEmbeddingService
from app.application.services.identity_directory import IIdentityDirectory
from app.application.services.milestone_extraction_ai_service import (
    IMilestoneExtractionAIService,
)
from app.application.services.recent_ranking_registry import RecentRankingRegistry
from app.application.services.reranker_service import IRerankerService
from app.application.services.smart_question_service import ISmartQuestionService
from app.application.services.tender_assistant_ai_service import (
    ITenderAssistantAIService,
)
from app.application.services.tender_refresher import ITenderRefresher
from app.application.services.token_cipher import ITokenCipher
from app.application.services.token_verifier import IAuthTokenVerifier
from app.application.use_cases.ask_tender_assistant_use_case import (
    AskTenderAssistantUseCase,
)
from app.application.use_cases.calendar.calendar_authorization import (
    CompleteCalendarAuthorizationUseCase,
    StartCalendarAuthorizationUseCase,
)
from app.application.use_cases.calendar.calendar_connections import (
    DisconnectCalendarUseCase,
    GetCalendarConnectionsUseCase,
)
from app.application.use_cases.calendar.refresh_synced_tender_dates import (
    RefreshSyncedTenderDatesUseCase,
)
from app.application.use_cases.calendar.sync_milestones import (
    SyncMilestonesToCalendarUseCase,
)
from app.application.use_cases.create_tender_chat_session_use_case import (
    CreateTenderChatSessionUseCase,
)
from app.application.use_cases.deep_analysis.get_or_create_deep_analysis import (
    GetOrCreateDeepAnalysisUseCase,
)
from app.application.use_cases.delete_tender_chat_document_use_case import (
    DeleteTenderChatDocumentUseCase,
)
from app.application.use_cases.get_tender_chat_history_use_case import (
    GetTenderChatHistoryUseCase,
)
from app.application.use_cases.list_tender_chat_documents_use_case import (
    ListTenderChatDocumentsUseCase,
)
from app.application.use_cases.matching.rank_tenders import RankTendersUseCase
from app.application.use_cases.matching.score_tender_on_demand import (
    ScoreTenderOnDemandUseCase,
)
from app.application.use_cases.milestones.extract_tender_milestones import (
    ExtractTenderMilestonesUseCase,
)
from app.application.use_cases.milestones.get_tender_milestones import (
    GetTenderMilestonesUseCase,
)
from app.application.use_cases.milestones.send_milestone_reminders import (
    SendMilestoneRemindersUseCase,
)
from app.application.use_cases.milestones.set_milestone_reminder import (
    SetMilestoneReminderUseCase,
)
from app.application.use_cases.notifications.build_daily_digest import (
    BuildDailyDigestUseCase,
)
from app.application.use_cases.notifications.dispatch_pending_deliveries import (
    DispatchPendingDeliveriesUseCase,
)
from app.application.use_cases.notifications.manage_notifications import (
    CountUnreadNotificationsUseCase,
    GetNotificationPreferencesUseCase,
    ListDeliveriesUseCase,
    ListNotificationsUseCase,
    MarkAllNotificationsReadUseCase,
    MarkNotificationReadUseCase,
    UpdateNotificationPreferencesUseCase,
)
from app.application.use_cases.notifications.scan_supplier_for_alerts import (
    ScanSupplierForAlertsUseCase,
)
from app.application.use_cases.questions.answer_question_use_case import (
    AnswerQuestionUseCase,
)
from app.application.use_cases.questions.smart_question_use_case import (
    SmartQuestionUseCase,
)
from app.application.use_cases.quotation import QuotationUseCase
from app.application.use_cases.ranking_telemetry.log_ranking_impressions import (
    LogRankingImpressionsUseCase,
    RankingImpressionLogger,
)
from app.application.use_cases.ranking_telemetry.record_tender_interaction import (
    RecordTenderInteractionUseCase,
)
from app.application.use_cases.ranking_telemetry.run_ranking_telemetry_cycle import (
    RankingTelemetryCycleResult,
)
from app.application.use_cases.saved_tenders.list_saved_tenders import (
    ListSavedTendersUseCase,
)
from app.application.use_cases.saved_tenders.save_tender import SaveTenderUseCase
from app.application.use_cases.saved_tenders.unsave_tender import UnsaveTenderUseCase
from app.application.use_cases.tender.get_tender_detail import (
    GetTenderDetailUseCase,
)
from app.application.use_cases.tender.search_tenders import SearchTendersUseCase
from app.application.use_cases.tender_attachments.complete_attachment_upload import (
    CompleteAttachmentUploadUseCase,
)
from app.application.use_cases.tender_attachments.delete_attachment_file import (
    DeleteAttachmentFileUseCase,
)
from app.application.use_cases.tender_attachments.get_tender_attachments import (
    GetTenderAttachmentsUseCase,
)
from app.application.use_cases.tender_attachments.promote_attachment import (
    AttachmentPromotionListener,
    PromoteAttachmentUseCase,
    PromoteOpener,
)
from app.application.use_cases.tender_attachments.request_attachment_upload import (
    RequestAttachmentUploadUseCase,
)
from app.application.use_cases.upload_tender_chat_document_use_case import (
    UploadTenderChatDocumentUseCase,
)
from app.config import settings
from app.domain.entities.calendar import CalendarProvider
from app.domain.entities.matching_result import MatchingResult
from app.infrastructure.auth.dependencies import (
    build_get_current_user,
    build_get_current_workspace_context,
    build_get_optional_workspace_context,
)
from app.infrastructure.db import async_session_maker, get_session
from app.infrastructure.repositories.calendar_repository import (
    CalendarConnectionRepository,
    CalendarEventLinkRepository,
    CalendarOAuthStateRepository,
)
from app.infrastructure.repositories.matching_result_repository import (
    MatchingResultRepository,
)
from app.infrastructure.repositories.notification_repository import (
    NotificationDeliveryRepository,
    NotificationPreferenceRepository,
    NotificationRepository,
)
from app.infrastructure.repositories.qdrant_supplier_repository import (
    QdrantSupplierRepository,
)
from app.infrastructure.repositories.qdrant_tender_item_vector_repository import (
    QdrantTenderItemVectorRepository,
)
from app.infrastructure.repositories.qdrant_tender_repository import (
    QdrantTenderRepository,
)
from app.infrastructure.repositories.question_repository import QuestionRepositoryImpl
from app.infrastructure.repositories.quotation_repository import QuotationRepository
from app.infrastructure.repositories.ranking_telemetry_repository import (
    SqlRankingTelemetryRepository,
)
from app.infrastructure.repositories.saved_tender_repository import (
    SavedTenderRepository,
)
from app.infrastructure.repositories.sql_attachment_extraction_repository import (
    SqlAttachmentExtractionRepository,
)
from app.infrastructure.repositories.sql_attachment_file_repository import (
    SqlAttachmentFileRepository,
)
from app.infrastructure.repositories.sql_attachment_processing_job_repository import (
    SqlAttachmentProcessingJobRepository,
)
from app.infrastructure.repositories.sql_attachment_processing_status_reader import (
    SqlAttachmentProcessingStatusReader,
)
from app.infrastructure.repositories.sql_attachment_trust_repository import (
    SqlAttachmentTrustRepository,
)
from app.infrastructure.repositories.sql_gemini_usage_repository import (
    SqlGeminiUsageRepository,
)
from app.infrastructure.repositories.sql_supplier_invitation_repository import (
    SqlSupplierInvitationRepository,
)
from app.infrastructure.repositories.sql_supplier_member_repository import (
    SqlSupplierMemberRepository,
)
from app.infrastructure.repositories.sql_tender_attachment_repository import (
    SqlTenderAttachmentRepository,
)
from app.infrastructure.repositories.sql_tender_digest_repository import (
    SqlTenderDigestRepository,
)
from app.infrastructure.repositories.sql_tender_chat_repository import (
    SQLTenderChatRepository,
)
from app.infrastructure.repositories.supplier_repository import SupplierRepository
from app.infrastructure.repositories.tender_milestone_repository import (
    TenderMilestoneRepository,
)
from app.infrastructure.repositories.tender_repository import TenderRepository
from app.infrastructure.repositories.user_repository import UserRepository
from app.infrastructure.routers.calendar import (
    create_calendar_router,
    create_milestone_sync_router,
)
from app.infrastructure.routers.dev_storage import create_dev_storage_router
from app.infrastructure.routers.milestones import create_milestones_router
from app.infrastructure.routers.quotation import create_quotation_router
from app.infrastructure.routers.router import create_router
from app.infrastructure.routers.tender_attachments import (
    create_tender_attachments_router,
)
from app.infrastructure.routers.tender_digest import (
    create_tender_digest_router,
)
from app.infrastructure.services.api_embedding_service import (
    ApiEmbeddingService,
    DeepInfraEmbeddingService,
    HuggingFaceEmbeddingService,
)
from app.infrastructure.services.api_reranker_service import ApiRerankerService
from app.infrastructure.services.attachment_processing_jobs import (
    sql_processing_units,
)
from app.infrastructure.services.attachment_processing_scheduler import (
    AsyncioProcessingSignal,
)
from app.infrastructure.services.attachments.content_reader import (
    StdlibAttachmentContentReader,
)
from app.infrastructure.services.attachments.local_attachment_storage import (
    LocalDiskAttachmentStorage,
)
from app.infrastructure.services.attachments.r2_attachment_storage import (
    R2AttachmentStorage,
)
from app.infrastructure.services.attachments.gemini_attachment_extraction_service import (
    GeminiAttachmentExtractionService,
)
from app.infrastructure.services.calendar.google_calendar_client import (
    GoogleCalendarClient,
)
from app.infrastructure.services.company_lookup.http_company_lookup_service import (
    HttpCompanyLookupService,
    SreLookupService,
    WebEmpresarioLookupService,
)
from app.infrastructure.services.document_validator_service import (
    DocumentValidatorService,
)
from app.infrastructure.services.gemini_deep_analysis_service import (
    GeminiDeepAnalysisService,
)
from app.infrastructure.services.gemini_milestone_extraction_service import (
    GeminiMilestoneExtractionService,
)
from app.infrastructure.services.gemini_document_analysis_and_quotation_service import (
    GeminiDocumentAnalysisAndQuotationService,
)
from app.infrastructure.services.gemini_tender_assistant_service import (
    GeminiTenderAssistantService,
)
from app.infrastructure.services.notifications.smtp_email_service import (
    SmtpEmailService,
)
from app.infrastructure.services.ranking_telemetry_jobs import (
    build_ranking_telemetry_cycle,
)
from app.infrastructure.services.security.fernet_token_cipher import (
    FernetTokenCipher,
    UnconfiguredTokenCipher,
)
from app.infrastructure.services.smart_question_service import SmartQuestionServiceImpl
from app.infrastructure.services.supabase_identity_directory import (
    SupabaseIdentityDirectory,
)
from app.infrastructure.services.supabase_token_service import (
    SupabaseJwtService,
    descargar_jwks,
)


def get_supplier_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ISupplierRepository:
    # Crea el repositorio concreto con la sesión de BD por petición
    return SupplierRepository(session)


def get_supplier_member_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ISupplierMemberRepository:
    return SqlSupplierMemberRepository(session)


def get_supplier_invitation_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ISupplierInvitationRepository:
    return SqlSupplierInvitationRepository(session)



def get_supplier_vector_repo(request: Request) -> ISupplierVectorRepository:
    # Reutiliza el cliente Qdrant inicializado en el lifespan
    return QdrantSupplierRepository(request.app.state.qdrant_async_client)


def get_tender_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ITenderRepository:
    # Crea el repositorio concreto de licitaciones con la sesión de BD
    return TenderRepository(session)


def get_embedding_service(request: Request) -> IEmbeddingService:
    return request.app.state.embedding_service


def get_company_lookup_service(request: Request) -> ICompanyLookupService | None:
    # `None` cuando COMPANY_LOOKUP_PROVIDER=none: el caso de uso responde 503.
    return request.app.state.company_lookup_service


def get_tender_vector_repo(request: Request) -> ITenderVectorRepository:
    return QdrantTenderRepository(
        client=request.app.state.qdrant_async_client,
        vector_size=settings.embedding_vector_size,
    )


def get_reranker_service(request: Request) -> IRerankerService:
    return request.app.state.reranker_service


def get_tender_item_vector_repo(request: Request) -> ITenderItemVectorRepository:
    # Como `get_tender_vector_repo`: el cliente Qdrant nace en el lifespan, que
    # corre después de `bootstrap(app)`, así que no se puede guardar en
    # `app.state` desde ahí y se arma el repositorio en cada petición.
    return QdrantTenderItemVectorRepository(
        client=request.app.state.qdrant_async_client,
        vector_size=settings.embedding_vector_size,
    )


def get_compatibility_formula(request: Request) -> CompatibilityFormula:
    return request.app.state.compatibility_formula


def get_matching_result_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IMatchingResultRepository:
    return MatchingResultRepository(session)


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


def get_compatibility_scorer(
    session: Annotated[AsyncSession, Depends(get_session)],
    reranker_service: Annotated[IRerankerService, Depends(get_reranker_service)],
    embedding_service: Annotated[IEmbeddingService, Depends(get_embedding_service)],
    item_vector_repo: Annotated[
        ITenderItemVectorRepository, Depends(get_tender_item_vector_repo)
    ],
    formula: Annotated[CompatibilityFormula, Depends(get_compatibility_formula)],
) -> CompatibilityScorer:
    """La fórmula de compatibilidad, compartida por el ranking y el cálculo a pedido."""
    return CompatibilityScorer(
        reranker_service=reranker_service,
        matching_result_repo=MatchingResultRepository(session),
        embedding_service=embedding_service,
        item_vector_repo=item_vector_repo,
        formula=formula,
        model_version=compatibility_model_version(),
    )


def get_rank_tenders_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
    supplier_vector_repo: Annotated[
        ISupplierVectorRepository, Depends(get_supplier_vector_repo)
    ],
    tender_vector_repo: Annotated[
        ITenderVectorRepository, Depends(get_tender_vector_repo)
    ],
    scorer: Annotated[CompatibilityScorer, Depends(get_compatibility_scorer)],
    embedding_service: Annotated[IEmbeddingService, Depends(get_embedding_service)],
    item_vector_repo: Annotated[
        ITenderItemVectorRepository, Depends(get_tender_item_vector_repo)
    ],
) -> RankTendersUseCase:
    return RankTendersUseCase(
        supplier_repo=SupplierRepository(session),
        supplier_vector_repo=supplier_vector_repo,
        tender_vector_repo=tender_vector_repo,
        tender_repo=TenderRepository(session),
        scorer=scorer,
        matching_result_repo=MatchingResultRepository(session),
        model_version=compatibility_model_version(),
        embedding_service=embedding_service,
        # Segundo canal de candidatas: las keywords contra las partidas.
        item_vector_repo=item_vector_repo,
    )


def get_score_tender_on_demand_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
    scorer: Annotated[CompatibilityScorer, Depends(get_compatibility_scorer)],
) -> ScoreTenderOnDemandUseCase:
    return ScoreTenderOnDemandUseCase(
        supplier_repo=SupplierRepository(session),
        tender_repo=TenderRepository(session),
        matching_result_repo=MatchingResultRepository(session),
        scorer=scorer,
    )


def get_quotation_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> QuotationUseCase:
    return QuotationUseCase(
        QuotationRepository(session),
        SupplierRepository(session),
        TenderRepository(session),
    )


def get_score_tender_on_demand_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
    scorer: Annotated[CompatibilityScorer, Depends(get_compatibility_scorer)],
) -> ScoreTenderOnDemandUseCase:
    return ScoreTenderOnDemandUseCase(
        supplier_repo=SupplierRepository(session),
        tender_repo=TenderRepository(session),
        matching_result_repo=MatchingResultRepository(session),
        scorer=scorer,
    )


def get_saved_tender_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ISavedTenderRepository:
    return SavedTenderRepository(session)


def get_list_saved_tenders_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ListSavedTendersUseCase:
    return ListSavedTendersUseCase(
        saved_tender_repo=SavedTenderRepository(session),
        tender_repo=TenderRepository(session),
        supplier_repo=SupplierRepository(session),
        matching_result_repo=MatchingResultRepository(session),
    )


def get_save_tender_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SaveTenderUseCase:
    return SaveTenderUseCase(
        saved_tender_repo=SavedTenderRepository(session),
        tender_repo=TenderRepository(session),
    )


def get_unsave_tender_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UnsaveTenderUseCase:
    return UnsaveTenderUseCase(saved_tender_repo=SavedTenderRepository(session))


def get_search_tenders_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
    supplier_vector_repo: Annotated[
        ISupplierVectorRepository, Depends(get_supplier_vector_repo)
    ],
    tender_vector_repo: Annotated[
        ITenderVectorRepository, Depends(get_tender_vector_repo)
    ],
    embedding_service: Annotated[IEmbeddingService, Depends(get_embedding_service)],
) -> SearchTendersUseCase:
    return SearchTendersUseCase(
        supplier_repo=SupplierRepository(session),
        supplier_vector_repo=supplier_vector_repo,
        tender_vector_repo=tender_vector_repo,
        tender_repo=TenderRepository(session),
        embedding_service=embedding_service,
    )


def get_tender_detail_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GetTenderDetailUseCase:
    return GetTenderDetailUseCase(
        tender_repo=TenderRepository(session),
        supplier_repo=SupplierRepository(session),
        matching_result_repo=MatchingResultRepository(session),
    )


# --- Alertas de licitaciones (HdU 08) ---


def get_notification_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> INotificationRepository:
    return NotificationRepository(session)


def get_notification_preference_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> INotificationPreferenceRepository:
    return NotificationPreferenceRepository(session)


def get_notification_delivery_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> INotificationDeliveryRepository:
    return NotificationDeliveryRepository(session)


def get_email_service(request: Request) -> IEmailService:
    return request.app.state.email_service


def get_list_notifications_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ListNotificationsUseCase:
    return ListNotificationsUseCase(
        notification_repo=NotificationRepository(session),
        tender_repo=TenderRepository(session),
    )


def get_count_unread_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CountUnreadNotificationsUseCase:
    return CountUnreadNotificationsUseCase(
        notification_repo=NotificationRepository(session)
    )


def get_mark_notification_read_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MarkNotificationReadUseCase:
    return MarkNotificationReadUseCase(
        notification_repo=NotificationRepository(session)
    )


def get_mark_all_read_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MarkAllNotificationsReadUseCase:
    return MarkAllNotificationsReadUseCase(
        notification_repo=NotificationRepository(session)
    )


def get_notification_preferences_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GetNotificationPreferencesUseCase:
    return GetNotificationPreferencesUseCase(
        preference_repo=NotificationPreferenceRepository(session)
    )


def get_update_notification_preferences_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UpdateNotificationPreferencesUseCase:
    return UpdateNotificationPreferencesUseCase(
        preference_repo=NotificationPreferenceRepository(session)
    )


def get_list_deliveries_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ListDeliveriesUseCase:
    return ListDeliveriesUseCase(delivery_repo=NotificationDeliveryRepository(session))


def get_user_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IUserRepository:
    return UserRepository(session)


def get_token_verifier(request: Request) -> IAuthTokenVerifier:
    """El verificador de tokens, como dependencia y no como objeto capturado.

    Que pase por el sistema de dependencias es lo que permite sustituirlo en los
    tests con `app.dependency_overrides`, y así ejercitar la verificación real
    contra un JWKS de prueba sin levantar Supabase.
    """
    return request.app.state.token_verifier


def get_identity_directory(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IIdentityDirectory:
    return SupabaseIdentityDirectory(session)


def get_deep_analysis_service(request: Request) -> IDeepAnalysisService:
    return request.app.state.deep_analysis_service


def get_get_or_create_deep_analysis_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
    deep_analysis_service: Annotated[
        IDeepAnalysisService, Depends(get_deep_analysis_service)
    ],
    scorer: Annotated[CompatibilityScorer, Depends(get_compatibility_scorer)],
) -> GetOrCreateDeepAnalysisUseCase:
    return GetOrCreateDeepAnalysisUseCase(
        supplier_repo=SupplierRepository(session),
        tender_repo=TenderRepository(session),
        matching_result_repo=MatchingResultRepository(session),
        deep_analysis_service=deep_analysis_service,
        scorer=scorer,
    )


def get_question_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IQuestionRepository:
    return QuestionRepositoryImpl(session)


def get_smart_question_service(
    question_repo: Annotated[IQuestionRepository, Depends(get_question_repo)],
) -> ISmartQuestionService:
    return SmartQuestionServiceImpl(question_repository=question_repo)


def get_smart_question_use_case(
    smart_question_service: Annotated[
        ISmartQuestionService, Depends(get_smart_question_service)
    ],
    supplier_repo: Annotated[ISupplierRepository, Depends(get_supplier_repo)],
) -> SmartQuestionUseCase:
    return SmartQuestionUseCase(
        smart_question_service=smart_question_service,
        supplier_repository=supplier_repo,
    )


def get_answer_question_use_case(
    supplier_repo: Annotated[ISupplierRepository, Depends(get_supplier_repo)],
) -> AnswerQuestionUseCase:
    # Inyectar el caso de uso que procesa las respuestas
    return AnswerQuestionUseCase(supplier_repo=supplier_repo)


def get_tender_chat_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ITenderChatRepository:
    return SQLTenderChatRepository(session)


def get_tender_assistant_ai_service(request: Request) -> ITenderAssistantAIService:
    return request.app.state.tender_assistant_ai_service


def get_milestone_extraction_service(request: Request) -> IMilestoneExtractionAIService:
    return request.app.state.milestone_extraction_service


def get_calendar_providers(request: Request) -> CalendarProviders:
    return request.app.state.calendar_providers


def get_token_cipher(request: Request) -> ITokenCipher:
    return request.app.state.token_cipher


def get_calendar_connection_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
    cipher: Annotated[ITokenCipher, Depends(get_token_cipher)],
) -> ICalendarConnectionRepository:
    return CalendarConnectionRepository(session, cipher)


def get_calendar_connections_use_case(
    connections: Annotated[ICalendarConnectionRepository, Depends(get_calendar_connection_repo)],
    providers: Annotated[CalendarProviders, Depends(get_calendar_providers)],
) -> GetCalendarConnectionsUseCase:
    return GetCalendarConnectionsUseCase(connections, providers)


def get_start_calendar_authorization_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
    providers: Annotated[CalendarProviders, Depends(get_calendar_providers)],
) -> StartCalendarAuthorizationUseCase:
    return StartCalendarAuthorizationUseCase(
        milestones=TenderMilestoneRepository(session),
        states=CalendarOAuthStateRepository(session),
        providers=providers,
    )


def get_complete_calendar_authorization_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
    connections: Annotated[ICalendarConnectionRepository, Depends(get_calendar_connection_repo)],
    providers: Annotated[CalendarProviders, Depends(get_calendar_providers)],
) -> CompleteCalendarAuthorizationUseCase:
    return CompleteCalendarAuthorizationUseCase(
        states=CalendarOAuthStateRepository(session),
        connections=connections,
        providers=providers,
    )


def get_sync_milestones_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
    connections: Annotated[ICalendarConnectionRepository, Depends(get_calendar_connection_repo)],
    providers: Annotated[CalendarProviders, Depends(get_calendar_providers)],
) -> SyncMilestonesToCalendarUseCase:
    return SyncMilestonesToCalendarUseCase(
        tenders=TenderRepository(session),
        milestones=TenderMilestoneRepository(session),
        connections=connections,
        event_links=CalendarEventLinkRepository(session),
        providers=providers,
        app_base_url=settings.app_base_url,
    )


def get_disconnect_calendar_use_case(
    connections: Annotated[ICalendarConnectionRepository, Depends(get_calendar_connection_repo)],
    providers: Annotated[CalendarProviders, Depends(get_calendar_providers)],
) -> DisconnectCalendarUseCase:
    return DisconnectCalendarUseCase(connections, providers)


def build_calendar_providers() -> dict[CalendarProvider, ICalendarProviderClient]:
    """Solo los proveedores con credenciales; sin ninguno, la sincronización queda apagada."""
    providers: dict[CalendarProvider, ICalendarProviderClient] = {}
    if settings.google_calendar_client_id and settings.google_calendar_client_secret:
        providers[CalendarProvider.GOOGLE] = GoogleCalendarClient(
            client_id=settings.google_calendar_client_id,
            client_secret=settings.google_calendar_client_secret,
            redirect_uri=settings.google_calendar_redirect_uri,
        )
    return providers


def get_tender_milestones_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
    chat_repo: Annotated[ITenderChatRepository, Depends(get_tender_chat_repo)],
) -> GetTenderMilestonesUseCase:
    return GetTenderMilestonesUseCase(
        tenders=TenderRepository(session),
        milestones=TenderMilestoneRepository(session),
        event_links=CalendarEventLinkRepository(session),
        chat=chat_repo,
    )


def get_tender_attachment_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ITenderAttachmentRepository:
    return SqlTenderAttachmentRepository(session)


def build_attachment_storage() -> IAttachmentStorage | None:
    """R2 si está configurado; disco local solo en desarrollo; si no, la subida queda apagada.

    Sin R2 y fuera de desarrollo devuelve `None`: la API arranca igual y las rutas
    de escritura responden 503 `storage_unavailable`, así se puede desplegar antes
    de crear el bucket sin romper nada.
    """
    if settings.r2_enabled:
        logger.info("Anexos en Cloudflare R2 (bucket %s).", settings.r2_bucket)
        return R2AttachmentStorage(
            account_id=settings.r2_account_id or "",
            access_key_id=settings.r2_access_key_id or "",
            secret_access_key=settings.r2_secret_access_key or "",
            bucket=settings.r2_bucket or "",
        )
    if settings.is_dev:
        logger.warning(
            "Anexos en disco local (%s): solo para desarrollo.",
            settings.attachment_local_storage_dir,
        )
        # Secreto por proceso: con --reload las URLs pendientes vencen, y el cliente
        # pide otra.
        return LocalDiskAttachmentStorage(
            root=Path(settings.attachment_local_storage_dir),
            public_base_url=settings.attachment_local_storage_public_url,
            secret=secrets.token_bytes(32),
        )
    logger.warning("Sin R2 configurado: la subida de anexos queda apagada.")
    return None


def get_attachment_storage(request: Request) -> IAttachmentStorage | None:
    return getattr(request.app.state, "attachment_storage", None)


def get_attachment_file_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IAttachmentFileRepository:
    return SqlAttachmentFileRepository(session)


def get_tender_digest_repo(request: Request) -> ITenderDigestRepository | None:
    return getattr(request.app.state, "tender_digest_repo", None)


def get_attachment_extraction_repo(
    request: Request,
) -> IAttachmentExtractionRepository | None:
    return getattr(request.app.state, "attachment_extraction_repo", None)


def get_gemini_usage_repo(request: Request) -> IGeminiUsageRepository | None:
    return getattr(request.app.state, "gemini_usage_repo", None)



def build_promotion_opener(
    storage: IAttachmentStorage | None,
    visibility_listener: IAttachmentVisibilityListener,
    session_factory: Callable[[], AsyncSession] = async_session_maker,
) -> PromoteOpener:
    """Entrega un caso de uso de promoción por evaluación, cada uno con su sesión.

    La promoción toma un candado sobre el anexo y hace su propio commit (decisión
    6): no puede usar la sesión de la petición, que puede traer cambios sin
    confirmar o quedar en un estado fallido por otro listener. Mismo patrón que
    `registrar_impresiones_de_ranking`.
    """

    @asynccontextmanager
    async def abrir() -> AsyncIterator[PromoteAttachmentUseCase]:
        async with session_factory() as session:
            yield PromoteAttachmentUseCase(
                trust=SqlAttachmentTrustRepository(session),
                storage=storage,
                visibility_listener=visibility_listener,
            )

    return abrir


def get_attachment_visibility_listener() -> IAttachmentVisibilityListener:
    # Decisión 4: reconstruir el resumen compartido cuando una versión entra o sale
    # de lo compartido. Hasta entonces, nadie escucha.
    return NoopAttachmentVisibilityListener()


def get_attachment_promotion_listener(
    storage: Annotated[IAttachmentStorage | None, Depends(get_attachment_storage)],
    visibility: Annotated[
        IAttachmentVisibilityListener, Depends(get_attachment_visibility_listener)
    ],
) -> AttachmentPromotionListener:
    return AttachmentPromotionListener(build_promotion_opener(storage, visibility))


def get_attachment_processing_notifier(
    request: Request,
) -> IAttachmentProcessingNotifier:
    return request.app.state.attachment_processing_signal


def get_attachment_processing_job_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IAttachmentProcessingJobRepository:
    return SqlAttachmentProcessingJobRepository(session)


def get_attachment_processing_status_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IAttachmentProcessingStatusReader:
    return SqlAttachmentProcessingStatusReader(session)


def get_attachment_stored_listener(
    promotion: Annotated[
        AttachmentPromotionListener, Depends(get_attachment_promotion_listener)
    ],
    jobs: Annotated[
        IAttachmentProcessingJobRepository | None,
        Depends(get_attachment_processing_job_repo),
    ] = None,
    notifier: Annotated[
        IAttachmentProcessingNotifier | None,
        Depends(get_attachment_processing_notifier),
    ] = None,
) -> IAttachmentStoredListener:
    # Decisión 6 (promoción) y Decisión 4 (extracción).
    listeners: list[IAttachmentStoredListener] = [promotion]
    if jobs is not None and notifier is not None:
        listeners.append(EnqueueExtractionOnStored(jobs=jobs, notifier=notifier))
    return CompositeAttachmentStoredListener(listeners)


def get_attachment_deleted_listener(
    promotion: Annotated[
        AttachmentPromotionListener, Depends(get_attachment_promotion_listener)
    ],
) -> IAttachmentDeletedListener:
    return CompositeAttachmentDeletedListener([promotion])


def get_tender_attachments_use_case(
    attachments: Annotated[
        ITenderAttachmentRepository, Depends(get_tender_attachment_repo)
    ],
    files: Annotated[IAttachmentFileRepository, Depends(get_attachment_file_repo)],
    storage: Annotated[IAttachmentStorage | None, Depends(get_attachment_storage)],
    status: Annotated[
        IAttachmentProcessingStatusReader | None,
        Depends(get_attachment_processing_status_reader),
    ] = None,
) -> GetTenderAttachmentsUseCase:
    return GetTenderAttachmentsUseCase(
        attachments,
        files,
        uploads_per_month=settings.attachment_manual_uploads_per_month,
        storage_available=storage is not None,
        processing=status,
        processing_enabled=settings.run_attachment_processing and storage is not None,
    )


def get_tender_digest_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GetTenderDigestUseCase:
    tenders = TenderRepository(session)
    extractions = SqlAttachmentExtractionRepository(session)
    return GetTenderDigestUseCase(
        tenders=tenders,
        extractions=extractions,
        status=SqlAttachmentProcessingStatusReader(session),
        build=BuildTenderDigestUseCase(
            tenders=tenders,
            extractions=extractions,
            digests=SqlTenderDigestRepository(session),
        ),
    )


def build_attachment_processing_runner(
    app: FastAPI,
) -> tuple[
    Callable[[], Awaitable[bool]],
    Callable[[], Awaitable[SweepResult]],
]:
    """El trabajo y el barrido del bucle del lifespan; cada fase abre y cierra su sesión."""
    units = sql_processing_units(async_session_maker)
    extract = ExtractAttachmentUseCase(
        units=units,
        storage=app.state.attachment_storage,
        reader=app.state.attachment_content_reader,
        ai=app.state.attachment_extraction_ai_service,
        daily_budget=settings.attachment_gemini_daily_budget,
    )
    signal = app.state.attachment_processing_signal
    return (
        ProcessNextAttachmentJobUseCase(
            units=units, extract=extract, notifier=signal
        ).execute,
        SweepAttachmentProcessingUseCase(units=units, notifier=signal).execute,
    )


def get_request_attachment_upload_use_case(
    attachments: Annotated[
        ITenderAttachmentRepository, Depends(get_tender_attachment_repo)
    ],
    files: Annotated[IAttachmentFileRepository, Depends(get_attachment_file_repo)],
    storage: Annotated[IAttachmentStorage | None, Depends(get_attachment_storage)],
    listener: Annotated[
        IAttachmentStoredListener, Depends(get_attachment_stored_listener)
    ],
) -> RequestAttachmentUploadUseCase:
    return RequestAttachmentUploadUseCase(
        attachments=attachments,
        files=files,
        storage=storage,
        listener=listener,
        uploads_per_month=settings.attachment_manual_uploads_per_month,
    )


def get_complete_attachment_upload_use_case(
    files: Annotated[IAttachmentFileRepository, Depends(get_attachment_file_repo)],
    storage: Annotated[IAttachmentStorage | None, Depends(get_attachment_storage)],
    listener: Annotated[
        IAttachmentStoredListener, Depends(get_attachment_stored_listener)
    ],
) -> CompleteAttachmentUploadUseCase:
    return CompleteAttachmentUploadUseCase(
        files=files, storage=storage, listener=listener
    )


def get_delete_attachment_file_use_case(
    files: Annotated[IAttachmentFileRepository, Depends(get_attachment_file_repo)],
    storage: Annotated[IAttachmentStorage | None, Depends(get_attachment_storage)],
    listener: Annotated[
        IAttachmentDeletedListener, Depends(get_attachment_deleted_listener)
    ],
) -> DeleteAttachmentFileUseCase:
    return DeleteAttachmentFileUseCase(files=files, storage=storage, listener=listener)


def get_set_milestone_reminder_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SetMilestoneReminderUseCase:
    return SetMilestoneReminderUseCase(TenderMilestoneRepository(session))


def get_extract_tender_milestones_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
    chat_repo: Annotated[ITenderChatRepository, Depends(get_tender_chat_repo)],
    ai: Annotated[IMilestoneExtractionAIService, Depends(get_milestone_extraction_service)],
    digest_repo: Annotated[
        ITenderDigestRepository | None, Depends(get_tender_digest_repo)
    ] = None,
    extraction_repo: Annotated[
        IAttachmentExtractionRepository | None, Depends(get_attachment_extraction_repo)
    ] = None,
) -> ExtractTenderMilestonesUseCase:
    return ExtractTenderMilestonesUseCase(
        tenders=TenderRepository(session),
        milestones=TenderMilestoneRepository(session),
        event_links=CalendarEventLinkRepository(session),
        chat=chat_repo,
        ai=ai,
        digest_repo=digest_repo,
        extraction_repo=extraction_repo,
    )


def get_document_validator_service() -> IDocumentValidatorService:
    return DocumentValidatorService()


def get_document_analysis_quotation_service(
    request: Request,
) -> IDocumentAnalysisAndQuotationService:
    return request.app.state.document_analysis_quotation_service


def get_upload_tender_chat_doc_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
    chat_repo: Annotated[ITenderChatRepository, Depends(get_tender_chat_repo)],
    validator_service: Annotated[
        IDocumentValidatorService, Depends(get_document_validator_service)
    ],
    unified_service: Annotated[
        IDocumentAnalysisAndQuotationService,
        Depends(get_document_analysis_quotation_service),
    ],
) -> UploadTenderChatDocumentUseCase:
    return UploadTenderChatDocumentUseCase(
        chat_repo=chat_repo,
        validator_service=validator_service,
        supplier_repo=SupplierRepository(session),
        tender_repo=TenderRepository(session),
        quotation_repo=QuotationRepository(session),
        matching_result_repo=MatchingResultRepository(session),
        unified_service=unified_service,
    )


def get_list_tender_chat_docs_use_case(
    chat_repo: Annotated[ITenderChatRepository, Depends(get_tender_chat_repo)],
) -> ListTenderChatDocumentsUseCase:
    return ListTenderChatDocumentsUseCase(chat_repo=chat_repo)


def get_delete_tender_chat_doc_use_case(
    chat_repo: Annotated[ITenderChatRepository, Depends(get_tender_chat_repo)],
) -> DeleteTenderChatDocumentUseCase:
    return DeleteTenderChatDocumentUseCase(chat_repo=chat_repo)


def get_ask_tender_assistant_use_case(
    chat_repo: Annotated[ITenderChatRepository, Depends(get_tender_chat_repo)],
    ai_service: Annotated[
        ITenderAssistantAIService, Depends(get_tender_assistant_ai_service)
    ],
    supplier_repo: Annotated[ISupplierRepository, Depends(get_supplier_repo)],
    tender_repo: Annotated[ITenderRepository, Depends(get_tender_repo)],
    validator_service: Annotated[
        IDocumentValidatorService, Depends(get_document_validator_service)
    ],
    digest_repo: Annotated[
        ITenderDigestRepository | None, Depends(get_tender_digest_repo)
    ] = None,
    extraction_repo: Annotated[
        IAttachmentExtractionRepository | None, Depends(get_attachment_extraction_repo)
    ] = None,
    attachment_file_repo: Annotated[
        IAttachmentFileRepository, Depends(get_attachment_file_repo)
    ] = None,
    attachment_storage: Annotated[
        IAttachmentStorage | None, Depends(get_attachment_storage)
    ] = None,
    usage_repo: Annotated[
        IGeminiUsageRepository | None, Depends(get_gemini_usage_repo)
    ] = None,
) -> AskTenderAssistantUseCase:
    return AskTenderAssistantUseCase(
        chat_repo=chat_repo,
        ai_service=ai_service,
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        validator_service=validator_service,
        digest_repo=digest_repo,
        extraction_repo=extraction_repo,
        attachment_file_repo=attachment_file_repo,
        attachment_storage=attachment_storage,
        usage_repo=usage_repo,
    )




def get_create_tender_chat_session_use_case(
    chat_repo: Annotated[ITenderChatRepository, Depends(get_tender_chat_repo)],
) -> CreateTenderChatSessionUseCase:
    return CreateTenderChatSessionUseCase(chat_repo=chat_repo)


def get_tender_chat_history_use_case(
    chat_repo: Annotated[ITenderChatRepository, Depends(get_tender_chat_repo)],
) -> GetTenderChatHistoryUseCase:
    return GetTenderChatHistoryUseCase(chat_repo=chat_repo)



class MockRerankerService(IRerankerService):
    """Reranker neutro para cuando está desactivado o falta ONNX en local/tests."""

    async def rerank(self, query_text, candidates, limit):
        return [(c[0], 1.0) for c in candidates][:limit]


logger = logging.getLogger(__name__)


async def registrar_impresiones_de_ranking(
    ranking_id: UUID,
    user_id: UUID,
    results: list[MatchingResult],
    served_at: datetime,
) -> None:
    """Escribe las posiciones servidas de un ranking.

    Corre como `BackgroundTask`, después de responder: abre su propia sesión (la
    de la petición ya puede estar cerrada) y nunca lanza, porque un fallo de
    telemetría no puede convertirse en un error para el usuario.
    """
    try:
        async with async_session_maker() as session:
            await LogRankingImpressionsUseCase(
                SqlRankingTelemetryRepository(session)
            ).execute(
                ranking_id=ranking_id,
                user_id=user_id,
                results=results,
                served_at=served_at,
            )
    except Exception as exc:
        # Sin `user_id` en el log: es un dato personal que no hace falta acá.
        logger.warning("No se pudo registrar el ranking %s: %s", ranking_id, exc)


def get_ranking_impression_logger() -> RankingImpressionLogger:
    return registrar_impresiones_de_ranking


def get_ranking_registry(request: Request) -> RecentRankingRegistry:
    return request.app.state.ranking_registry


def get_record_tender_interaction_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RecordTenderInteractionUseCase:
    return RecordTenderInteractionUseCase(repo=SqlRankingTelemetryRepository(session))


def build_ranking_telemetry_runner() -> Callable[
    [], Awaitable[RankingTelemetryCycleResult]
]:
    """El ciclo del bucle del lifespan: abre y cierra su propia sesión en cada trabajo."""
    return build_ranking_telemetry_cycle(async_session_maker)


class MockEmbeddingService(IEmbeddingService):
    """Embeddings en cero, para levantar en local sin el modelo descargado.

    Con él toda búsqueda y todo matching devuelven resultados sin sentido, y la
    aplicación se ve perfectamente sana desde afuera. Por eso vive solo en
    desarrollo y grita en los logs.
    """

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * settings.embedding_vector_size for _ in texts]


# Cada proveedor habla su propio dialecto HTTP; el mapa evita un if por cada uno.
# Los valores posibles los acota el Literal de `Settings.embedding_provider`, así que
# una clave faltante es un error de programación, no de configuración.
_EMBEDDING_POR_PROVEEDOR: dict[str, type[ApiEmbeddingService]] = {
    "deepinfra": DeepInfraEmbeddingService,
    "huggingface": HuggingFaceEmbeddingService,
}


def build_embedding_service() -> IEmbeddingService:
    """Construye el servicio de embeddings según el proveedor configurado.

    Mismo criterio que el reranker, y por la misma razón: antes esto caía a
    `MockEmbeddingService` con un `logger.warning` incluso en producción. Un
    despliegue donde el modelo no carga quedaba "exitoso", respondiendo con
    vectores de puros ceros —y peor, la ingesta los escribía en Qdrant, que no
    se arregla corrigiendo la configuración: hay que reindexar.
    """
    if settings.embedding_provider != "local":
        logger.info(
            "Embeddings servidos por %s (%s).",
            settings.embedding_provider,
            settings.embedding_model,
        )
        return _EMBEDDING_POR_PROVEEDOR[settings.embedding_provider](
            api_key=settings.embedding_api_key or "",
            base_url=settings.embedding_api_url,
            model_name=settings.embedding_model,
        )

    try:
        # Importación tardía: sentence-transformers no está en la imagen de
        # producción cuando se corre en modo API.
        from app.infrastructure.services.bge_m3_embedding_service import (
            BgeM3EmbeddingService,
        )

        return BgeM3EmbeddingService(model_name=settings.embedding_model)
    except Exception as exc:
        if not settings.is_dev:
            logger.exception(
                "El servicio de embeddings no se pudo construir (%s) y "
                "IS_DEV=false, así que la aplicación no arranca. Degradarse en "
                "silencio serviría búsquedas y matching sin ningún sentido.",
                exc,
            )
            raise

        logger.exception(
            "El servicio de embeddings no se pudo construir (%s). Se continúa "
            "con MockEmbeddingService porque IS_DEV=true, pero las búsquedas y "
            "el matching no tienen sentido hasta que esto se resuelva.",
            exc,
        )
        return MockEmbeddingService()


def build_reranker_service() -> IRerankerService:
    """Construye el reranker, o decide qué hacer si no se puede.

    `MockRerankerService` devuelve 1.0 para todas las candidatas: con él la
    aplicación responde igual, pero el orden de las recomendaciones es
    arbitrario. Es una degradación que no se nota desde afuera, así que la
    única defensa es que quede escrita en los logs.

    Por eso el fallback vive solo en desarrollo. Fuera de ahí un reranker que
    no arranca es un fallo de arranque: mejor no levantar que servir
    recomendaciones en orden aleatorio sin que nadie se entere.
    """
    if settings.disable_reranker:
        logger.warning(
            "Reranker desactivado por configuración (DISABLE_RERANKER). "
            "Se usa MockRerankerService y las recomendaciones no van ordenadas."
        )
        return MockRerankerService()

    if settings.reranker_provider != "local":
        # Sin try/except: config.py ya garantizó que hay credencial, y construir
        # el cliente no toca la red. Un fallo acá sería un error de programación,
        # no una condición del entorno que tenga sentido absorber.
        logger.info("Reranker servido por API (%s).", settings.pinecone_rerank_model)
        return ApiRerankerService(
            api_key=settings.pinecone_api_key or "",
            base_url=settings.pinecone_base_url,
            model_name=settings.pinecone_rerank_model,
            api_version=settings.pinecone_api_version,
        )

    try:
        # Importación tardía: arrastra onnxruntime y transformers, que en modo
        # API no están instalados en la imagen.
        from app.infrastructure.services.bge_reranker_service import (
            BgeRerankerService,
        )

        return BgeRerankerService()
    except Exception as exc:
        # En producción no se traga: relanza y el arranque falla con la traza.
        if not settings.is_dev:
            logger.exception(
                "El reranker no se pudo construir (%s) y IS_DEV=false, así que "
                "la aplicación no arranca. Degradarse en silencio serviría "
                "recomendaciones en orden arbitrario.",
                exc,
            )
            raise

        # En local sí: falta de RAM u ONNX no debería impedir levantar la API.
        logger.exception(
            "El reranker no se pudo construir (%s). Se continúa con "
            "MockRerankerService porque IS_DEV=true, pero las recomendaciones "
            "van en orden arbitrario hasta que esto se resuelva.",
            exc,
        )
        return MockRerankerService()


_FUENTE_DE_EMPRESAS_POR_PROVEEDOR: dict[str, type[HttpCompanyLookupService]] = {
    "sre": SreLookupService,
    "web-empresario": WebEmpresarioLookupService,
}


def build_company_lookup_service() -> ICompanyLookupService | None:
    """Fuente de datos de empresas para importar el perfil por RUT (HdU 16).

    Sin fuente configurada devuelve `None` y la importación queda apagada: es una
    ayuda del wizard, no algo de lo que dependa crear la empresa. La credencial ya
    la exigió `config.py` y construir el cliente no toca la red.
    """
    if settings.company_lookup_provider == "none":
        logger.info("Importación de perfil por RUT desactivada (COMPANY_LOOKUP_PROVIDER=none).")
        return None

    logger.info("Importación de perfil por RUT servida por %s.", settings.company_lookup_provider)
    return _FUENTE_DE_EMPRESAS_POR_PROVEEDOR[settings.company_lookup_provider](
        api_key=settings.company_lookup_api_key or "",
        base_url=settings.company_lookup_url,
    )


def build_milestone_refresh_runner(
    app: FastAPI, refresher: ITenderRefresher
) -> Callable[[], Awaitable[int]]:
    """Arma la función que ejecuta `MilestoneRefreshScheduler` (HU-16).

    Como los runners de alertas, abre su propia sesión en cada vuelta: vive
    fuera del ciclo de petición de FastAPI.
    """

    async def refresh() -> int:
        async with async_session_maker() as session:
            tenders = TenderRepository(session)
            milestones = TenderMilestoneRepository(session)
            event_links = CalendarEventLinkRepository(session)
            sync = SyncMilestonesToCalendarUseCase(
                tenders=tenders,
                milestones=milestones,
                connections=CalendarConnectionRepository(session, app.state.token_cipher),
                event_links=event_links,
                providers=app.state.calendar_providers,
                app_base_url=settings.app_base_url,
            )
            return await RefreshSyncedTenderDatesUseCase(
                tenders=tenders,
                refresher=refresher,
                milestones=milestones,
                event_links=event_links,
                sync=sync,
                notifications=NotificationRepository(session),
                deliveries=NotificationDeliveryRepository(session),
                preferences=NotificationPreferenceRepository(session),
            ).execute()

    return refresh


def build_notification_runners(
    app: FastAPI,
) -> tuple[
    Callable[[], Awaitable[int]],
    Callable[[], Awaitable[int]],
    Callable[[], Awaitable[int]],
    Callable[[], Awaitable[int]],
]:
    """Arma las cuatro funciones que ejecuta `NotificationScheduler`.

    Los bucles viven fuera del ciclo de petición de FastAPI, así que no pueden
    apoyarse en `Depends(get_session)`: cada ejecución abre y cierra su propia
    sesión. Se hace acá, en el composition root, para que el scheduler no
    conozca ningún repositorio concreto.
    """

    def _rank_tenders(session: AsyncSession) -> RankTendersUseCase:
        item_vector_repo = QdrantTenderItemVectorRepository(
            client=app.state.qdrant_async_client,
            vector_size=settings.embedding_vector_size,
        )
        return RankTendersUseCase(
            supplier_repo=SupplierRepository(session),
            supplier_vector_repo=QdrantSupplierRepository(app.state.qdrant_async_client),
            tender_vector_repo=QdrantTenderRepository(
                client=app.state.qdrant_async_client,
                vector_size=settings.embedding_vector_size,
            ),
            tender_repo=TenderRepository(session),
            scorer=CompatibilityScorer(
                reranker_service=app.state.reranker_service,
                matching_result_repo=MatchingResultRepository(session),
                embedding_service=app.state.embedding_service,
                item_vector_repo=item_vector_repo,
                formula=app.state.compatibility_formula,
                model_version=compatibility_model_version(),
            ),
            matching_result_repo=MatchingResultRepository(session),
            model_version=compatibility_model_version(),
            # El escaneo reescribe el mismo ranking que ve el usuario: tiene que
            # buscar candidatas con las mismas piezas que el endpoint, incluido el
            # segundo canal (keywords contra partidas), que necesita ambas.
            embedding_service=app.state.embedding_service,
            item_vector_repo=item_vector_repo,
        )

    async def scan_all() -> int:
        async with async_session_maker() as session:
            user_ids = await SupplierRepository(session).list_user_ids_with_profile()

        total = 0
        for user_id in user_ids:
            try:
                async with async_session_maker() as session:
                    use_case = ScanSupplierForAlertsUseCase(
                        rank_tenders_use_case=_rank_tenders(session),
                        preference_repo=NotificationPreferenceRepository(session),
                        notification_repo=NotificationRepository(session),
                        delivery_repo=NotificationDeliveryRepository(session),
                    )
                    total += len(await use_case.execute(user_id))
            except Exception as e:
                # Un proveedor sin vector en Qdrant, o cualquier otro fallo
                # puntual, no puede detener el escaneo del resto.
                logger.warning("No se pudo escanear al usuario %s: %s", user_id, e)

            # El reranker es CPU y la API corre con un solo worker: sin esta
            # pausa, un escaneo largo dejaría las peticiones esperando.
            await asyncio.sleep(1)
        return total

    async def dispatch_pending() -> int:
        async with async_session_maker() as session:
            use_case = DispatchPendingDeliveriesUseCase(
                delivery_repo=NotificationDeliveryRepository(session),
                notification_repo=NotificationRepository(session),
                preference_repo=NotificationPreferenceRepository(session),
                user_repo=UserRepository(session),
                tender_repo=TenderRepository(session),
                email_service=app.state.email_service,
                base_url=settings.app_base_url,
            )
            return await use_case.execute()

    async def build_digest() -> int:
        async with async_session_maker() as session:
            use_case = BuildDailyDigestUseCase(
                preference_repo=NotificationPreferenceRepository(session),
                notification_repo=NotificationRepository(session),
                delivery_repo=NotificationDeliveryRepository(session),
            )
            return await use_case.execute()

    async def send_milestone_reminders() -> int:
        async with async_session_maker() as session:
            use_case = SendMilestoneRemindersUseCase(
                tenders=TenderRepository(session),
                milestones=TenderMilestoneRepository(session),
                notifications=NotificationRepository(session),
                deliveries=NotificationDeliveryRepository(session),
                preferences=NotificationPreferenceRepository(session),
            )
            return await use_case.execute()

    return scan_all, dispatch_pending, build_digest, send_milestone_reminders


def bootstrap(app: FastAPI) -> None:
    # El backend ya no emite sesiones: las verifica. La instancia vive en
    # app.state porque cachea el JWKS de Supabase, y una por petición
    # descargaría las claves en cada llamada.
    app.state.token_verifier = SupabaseJwtService(
        jwks_source=lambda: descargar_jwks(settings.jwks_url),
        issuer=settings.jwt_issuer,
        audience=settings.supabase_jwt_audience,
        cache_seconds=settings.supabase_jwks_cache_seconds,
    )

    app.state.embedding_service = build_embedding_service()

    app.state.deep_analysis_service = GeminiDeepAnalysisService(
        api_key=settings.gemini_api_key,
        model_name=settings.gemini_model,
    )
    app.state.tender_assistant_ai_service = GeminiTenderAssistantService(
        api_key=settings.gemini_api_key,
        model_name=settings.gemini_model,
    )
    app.state.milestone_extraction_service = GeminiMilestoneExtractionService(
        api_key=settings.gemini_api_key,
        model_name=settings.gemini_model,
    )
    app.state.document_analysis_quotation_service = (
        GeminiDocumentAnalysisAndQuotationService(
            api_key=settings.gemini_api_key,
            model_name=settings.gemini_model,
        )
    )
    # Una llave inválida corta el arranque acá, no al guardar el primer token.
    app.state.token_cipher = (
        FernetTokenCipher(settings.token_encryption_key)
        if settings.token_encryption_key
        else UnconfiguredTokenCipher()
    )
    app.state.calendar_providers = build_calendar_providers()

    app.state.reranker_service = build_reranker_service()

    app.state.company_lookup_service = build_company_lookup_service()

    # El envío de correo es stateless y barato de construir, pero vive en
    # app.state igual que el resto: así el scheduler y los endpoints usan
    # exactamente la misma instancia configurada.
    app.state.email_service = SmtpEmailService(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        sender=settings.smtp_from,
        use_tls=settings.smtp_use_tls,
    )

    # Los coeficientes son inmutables y salen de la configuración, así que una
    # sola instancia sirve a todas las peticiones. El repositorio de vectores de
    # partidas no se registra acá: necesita el cliente Qdrant, que el lifespan
    # crea después (ver `get_tender_item_vector_repo`).
    #
    # La región no pondera: `RankTendersUseCase` ya descarta las licitaciones
    # fuera de las regiones del proveedor, así que un bono adicional se lo
    # llevarían todas las que sobreviven al filtro y no ordenaría nada.
    app.state.compatibility_formula = build_compatibility_formula()

    # En memoria y por proceso (un solo worker): reusa el `ranking_id` cuando se
    # sirve la misma lista al mismo usuario y empresa en 30 minutos.
    app.state.ranking_registry = RecentRankingRegistry()

    # R2, disco local (solo desarrollo) o nada. Antes de los routers: ellos y los
    # casos de uso lo leen de `app.state`.
    app.state.attachment_storage = build_attachment_storage()
    app.state.attachment_extraction_ai_service = (
        GeminiAttachmentExtractionService(
            api_key=settings.gemini_api_key,
            model_name=settings.attachment_extraction_model,
        )
    )
    app.state.attachment_content_reader = StdlibAttachmentContentReader()
    # Un solo despertador por proceso: lo comparten el listener (peticiones) y el bucle.
    app.state.attachment_processing_signal = AsyncioProcessingSignal()

    # Una sola instancia de la dependencia → FastAPI cachea el usuario por request
    get_current_user = build_get_current_user(
        get_user_repo=get_user_repo,
        get_token_verifier=get_token_verifier,
        get_identity_directory=get_identity_directory,
    )

    get_current_workspace_context = build_get_current_workspace_context(
        get_current_user=get_current_user,
        get_member_repo=get_supplier_member_repo,
        get_supplier_repo=get_supplier_repo,
    )
    get_optional_workspace_context = build_get_optional_workspace_context(
        get_current_user=get_current_user,
        get_member_repo=get_supplier_member_repo,
        get_supplier_repo=get_supplier_repo,
    )

    router = create_router(
        get_rank_tenders_use_case=get_rank_tenders_use_case,
        get_smart_question_use_case=get_smart_question_use_case,
        get_answer_question_use_case=get_answer_question_use_case,
        get_supplier_repo=get_supplier_repo,
        get_supplier_vector_repo=get_supplier_vector_repo,
        get_embedding_service=get_embedding_service,
        get_company_lookup_service=get_company_lookup_service,
        get_user_repo=get_user_repo,
        get_current_user=get_current_user,
        get_supplier_member_repo=get_supplier_member_repo,
        get_supplier_invitation_repo=get_supplier_invitation_repo,
        get_current_workspace_context=get_current_workspace_context,
        get_optional_workspace_context=get_optional_workspace_context,
        get_get_or_create_deep_analysis_use_case=get_get_or_create_deep_analysis_use_case,
        get_list_saved_tenders_use_case=get_list_saved_tenders_use_case,
        get_save_tender_use_case=get_save_tender_use_case,
        get_unsave_tender_use_case=get_unsave_tender_use_case,
        get_search_tenders_use_case=get_search_tenders_use_case,
        get_tender_detail_use_case=get_tender_detail_use_case,
        get_score_tender_on_demand_use_case=get_score_tender_on_demand_use_case,
        get_list_notifications_use_case=get_list_notifications_use_case,
        get_count_unread_use_case=get_count_unread_use_case,
        get_mark_notification_read_use_case=get_mark_notification_read_use_case,
        get_mark_all_read_use_case=get_mark_all_read_use_case,
        get_notification_preferences_use_case=get_notification_preferences_use_case,
        get_update_notification_preferences_use_case=get_update_notification_preferences_use_case,
        get_list_deliveries_use_case=get_list_deliveries_use_case,
        get_upload_tender_chat_doc_use_case=get_upload_tender_chat_doc_use_case,
        get_list_tender_chat_docs_use_case=get_list_tender_chat_docs_use_case,
        get_delete_tender_chat_doc_use_case=get_delete_tender_chat_doc_use_case,
        get_ask_tender_assistant_use_case=get_ask_tender_assistant_use_case,
        get_tender_chat_history_use_case=get_tender_chat_history_use_case,
        get_create_tender_chat_session_use_case=get_create_tender_chat_session_use_case,
        get_email_service=get_email_service,
        get_ranking_impression_logger=get_ranking_impression_logger,
        get_ranking_registry=get_ranking_registry,
        get_record_tender_interaction_use_case=get_record_tender_interaction_use_case,
    )
    app.include_router(router)
    app.include_router(
        create_quotation_router(
            get_current_user,
            get_quotation_use_case,
            get_current_workspace_context=get_optional_workspace_context,
        )
    )
    app.include_router(
        create_milestones_router(
            get_current_user,
            get_tender_milestones_use_case,
            get_extract_tender_milestones_use_case,
            get_set_milestone_reminder_use_case,
        )
    )
    app.include_router(
        create_calendar_router(
            get_current_user,
            get_calendar_connections_use_case,
            get_start_calendar_authorization_use_case,
            get_complete_calendar_authorization_use_case,
            get_disconnect_calendar_use_case,
        )
    )
    app.include_router(
        create_milestone_sync_router(get_current_user, get_sync_milestones_use_case)
    )
    app.include_router(
        create_tender_attachments_router(
            get_current_user,
            get_tender_attachments_use_case,
            get_optional_workspace_context=get_optional_workspace_context,
            get_current_workspace_context=get_current_workspace_context,
            get_request_upload_use_case=get_request_attachment_upload_use_case,
            get_complete_upload_use_case=get_complete_attachment_upload_use_case,
            get_delete_file_use_case=get_delete_attachment_file_use_case,
        )
    )
    app.include_router(
        create_tender_digest_router(
            get_current_user,
            get_tender_digest_use_case,
            get_optional_workspace_context=get_optional_workspace_context,
        )
    )
    # El receptor de subidas del disco local solo existe cuando de verdad se usa
    # el disco local: nunca con R2 ni en producción.
    if isinstance(app.state.attachment_storage, LocalDiskAttachmentStorage):
        app.include_router(create_dev_storage_router(app.state.attachment_storage))

