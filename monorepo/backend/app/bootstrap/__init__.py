import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.calendar_repository import (
    ICalendarConnectionRepository,
    ICalendarEventLinkRepository,
    ICalendarOAuthStateRepository,
)
from app.application.repositories.capability_repository import (
    ICapabilityAnswerRepository,
    ICapabilityEvidenceRepository,
    ICapabilityQuestionRepository,
)
from app.application.repositories.export_job_repository import IExportJobRepository
from app.application.repositories.kanban_repository import (
    IKanbanCardRepository,
    IKanbanColumnRepository,
)
from app.application.repositories.matching_result_repository import (
    IMatchingResultRepository,
)
from app.application.repositories.notification_repository import (
    INotificationDeliveryRepository,
    INotificationPreferenceRepository,
    INotificationRepository,
)
from app.application.repositories.proposal_repository import IProposalDraftRepository
from app.application.repositories.question_repository import IQuestionRepository
from app.application.repositories.quotation_repository import IQuotationRepository
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
from app.application.repositories.tender_chat_repository import (
    ITenderChatRepository,
)
from app.application.repositories.tender_milestone_repository import (
    ITenderMilestoneRepository,
)
from app.application.repositories.tender_repository import ITenderRepository
from app.application.repositories.tender_share_link_repository import (
    ITenderShareLinkRepository,
)
from app.application.repositories.tender_vector_repository import (
    ITenderVectorRepository,
)
from app.application.repositories.user_repository import IUserRepository
from app.application.services.calendar_provider_client import (
    CalendarProviders,
    ICalendarProviderClient,
)
from app.application.services.company_lookup_service import ICompanyLookupService
from app.application.services.compatibility_scorer import CompatibilityScorer
from app.application.services.deep_analysis_service import IDeepAnalysisService
from app.application.services.document_validator_service import (
    IDocumentValidatorService,
)
from app.application.services.email_service import IEmailService
from app.application.services.embedding_service import IEmbeddingService
from app.application.services.export_background import IExportBackground
from app.application.services.identity_directory import IIdentityDirectory
from app.application.services.milestone_extraction_ai_service import (
    IMilestoneExtractionAIService,
)
from app.application.services.proposal_ai_service import IProposalAIService
from app.application.services.reranker_service import IRerankerService
from app.application.services.smart_question_service import ISmartQuestionService
from app.application.services.tender_assistant_ai_service import (
    ITenderAssistantAIService,
)
from app.application.services.tender_refresher import ITenderRefresher
from app.application.services.token_cipher import ITokenCipher
from app.application.services.token_verifier import IAuthTokenVerifier
from app.application.services.weighting_service import IWeightingService
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
from app.application.use_cases.capabilities.add_capability_evidence import (
    AddCapabilityEvidenceUseCase,
)
from app.application.use_cases.capabilities.answer_capability_question import (
    AnswerCapabilityQuestionUseCase,
)
from app.application.use_cases.capabilities.build_experience_catalog import (
    BuildExperienceCatalogUseCase,
)
from app.application.use_cases.capabilities.list_pending_questions import (
    ListPendingCapabilityQuestionsUseCase,
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
from app.application.use_cases.exports.build_export_snapshot import (
    BuildExportSnapshotUseCase,
)
from app.application.use_cases.exports.export_jobs import (
    CompleteExportJobUseCase,
    DownloadExportFileUseCase,
    GetExportJobUseCase,
    ReconcileExportJobsUseCase,
)
from app.application.use_cases.exports.export_tender import ExportTenderUseCase
from app.application.use_cases.get_tender_chat_history_use_case import (
    GetTenderChatHistoryUseCase,
)
from app.application.use_cases.kanban.add_tender_to_board import AddTenderToBoardUseCase
from app.application.use_cases.kanban.create_kanban_column import (
    CreateKanbanColumnUseCase,
)
from app.application.use_cases.kanban.delete_kanban_column import (
    DeleteKanbanColumnUseCase,
)
from app.application.use_cases.kanban.list_kanban_cards import ListKanbanCardsUseCase
from app.application.use_cases.kanban.list_kanban_columns import (
    ListKanbanColumnsUseCase,
)
from app.application.use_cases.kanban.move_kanban_card import MoveKanbanCardUseCase
from app.application.use_cases.kanban.remove_tender_from_board import (
    RemoveTenderFromBoardUseCase,
)
from app.application.use_cases.kanban.update_kanban_column import (
    UpdateKanbanColumnUseCase,
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
from app.application.use_cases.proposals.answer_proposal_question import (
    AnswerProposalQuestionUseCase,
)
from app.application.use_cases.proposals.decide_discrepancy import (
    DecideDiscrepancyUseCase,
)
from app.application.use_cases.proposals.export_proposal import (
    ExportProposalDocxUseCase,
)
from app.application.use_cases.proposals.generate_proposal import (
    GenerateProposalUseCase,
)
from app.application.use_cases.proposals.get_proposal import GetProposalUseCase
from app.application.use_cases.proposals.regenerate_proposal import (
    RegenerateProposalUseCase,
)
from app.application.use_cases.proposals.resume_proposal import ResumeProposalUseCase
from app.application.use_cases.proposals.start_feasibility import (
    StartFeasibilityUseCase,
)
from app.application.use_cases.proposals.sync_proposal_answers import (
    SyncProposalAnswersUseCase,
)
from app.application.use_cases.questions.answer_question_use_case import (
    AnswerQuestionUseCase,
)
from app.application.use_cases.questions.smart_question_use_case import (
    SmartQuestionUseCase,
)
from app.application.use_cases.quotation import QuotationUseCase
from app.application.use_cases.saved_tenders.list_saved_tenders import (
    ListSavedTendersUseCase,
)
from app.application.use_cases.saved_tenders.save_tender import SaveTenderUseCase
from app.application.use_cases.saved_tenders.unsave_tender import UnsaveTenderUseCase
from app.application.use_cases.sharing.tender_sharing import (
    CreateShareLinkUseCase,
    GetSharedTenderUseCase,
    ListShareLinksUseCase,
    RevokeShareLinkUseCase,
)
from app.application.use_cases.tender.get_tender_detail import (
    GetTenderDetailUseCase,
)
from app.application.use_cases.tender.search_tenders import SearchTendersUseCase
from app.application.use_cases.upload_tender_chat_document_use_case import (
    UploadTenderChatDocumentUseCase,
)
from app.config import settings
from app.domain.entities.calendar import CalendarProvider
from app.infrastructure.db import async_session_maker, get_session
from app.infrastructure.repositories.calendar_repository import (
    CalendarConnectionRepository,
    CalendarEventLinkRepository,
    CalendarOAuthStateRepository,
)
from app.infrastructure.repositories.export_job_repository import ExportJobRepository
from app.infrastructure.repositories.kanban_repository import (
    KanbanCardRepository,
    KanbanColumnRepository,
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
from app.infrastructure.repositories.qdrant_tender_repository import (
    QdrantTenderRepository,
)
from app.infrastructure.repositories.question_repository import QuestionRepositoryImpl
from app.infrastructure.repositories.quotation_repository import QuotationRepository
from app.infrastructure.repositories.saved_tender_repository import (
    SavedTenderRepository,
)
from app.infrastructure.repositories.sql_capability_repository import (
    SqlCapabilityAnswerRepository,
    SqlCapabilityEvidenceRepository,
    SqlCapabilityQuestionRepository,
)
from app.infrastructure.repositories.sql_proposal_repository import (
    SqlProposalDraftRepository,
)
from app.infrastructure.repositories.sql_supplier_invitation_repository import (
    SqlSupplierInvitationRepository,
)
from app.infrastructure.repositories.sql_supplier_member_repository import (
    SqlSupplierMemberRepository,
)
from app.infrastructure.repositories.sql_tender_chat_repository import (
    SQLTenderChatRepository,
)
from app.infrastructure.repositories.supplier_repository import SupplierRepository
from app.infrastructure.repositories.tender_milestone_repository import (
    TenderMilestoneRepository,
)
from app.infrastructure.repositories.tender_repository import TenderRepository
from app.infrastructure.repositories.tender_share_link_repository import (
    TenderShareLinkRepository,
)
from app.infrastructure.repositories.user_repository import UserRepository
from app.infrastructure.services.api_embedding_service import (
    ApiEmbeddingService,
    DeepInfraEmbeddingService,
    HuggingFaceEmbeddingService,
)
from app.infrastructure.services.api_reranker_service import ApiRerankerService
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
from app.infrastructure.services.docx_proposal_exporter import DocxProposalExporter
from app.infrastructure.services.exports.background import AsyncioExportBackground
from app.infrastructure.services.exports.excel_renderer import OpenpyxlExcelRenderer
from app.infrastructure.services.exports.pdf_renderer import ReportLabPdfRenderer
from app.infrastructure.services.field_weighting_service import FieldWeightingService
from app.infrastructure.services.gemini_deep_analysis_service import (
    GeminiDeepAnalysisService,
)
from app.infrastructure.services.gemini_milestone_extraction_service import (
    GeminiMilestoneExtractionService,
)
from app.infrastructure.services.gemini_proposal_service import GeminiProposalService
from app.infrastructure.services.gemini_tender_assistant_service import (
    GeminiTenderAssistantService,
)
from app.infrastructure.services.notifications.smtp_email_service import (
    SmtpEmailService,
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

# --- Repositorios SQL ---
#
# Uno por repositorio, todos sobre la sesión de la petición. FastAPI cachea
# `get_session` dentro de un request, así que todos comparten la misma sesión y
# transacción. Los casos de uso los piden por estos providers, y no instanciando
# el repositorio, para que un `dependency_overrides` sobre uno de ellos alcance
# a todos los endpoints que lo usan.

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_supplier_repo(session: SessionDep) -> ISupplierRepository:
    return SupplierRepository(session)


def get_supplier_member_repo(session: SessionDep) -> ISupplierMemberRepository:
    return SqlSupplierMemberRepository(session)


def get_supplier_invitation_repo(session: SessionDep) -> ISupplierInvitationRepository:
    return SqlSupplierInvitationRepository(session)


def get_user_repo(session: SessionDep) -> IUserRepository:
    return UserRepository(session)


def get_tender_repo(session: SessionDep) -> ITenderRepository:
    return TenderRepository(session)


def get_matching_result_repo(session: SessionDep) -> IMatchingResultRepository:
    return MatchingResultRepository(session)


def get_saved_tender_repo(session: SessionDep) -> ISavedTenderRepository:
    return SavedTenderRepository(session)


def get_notification_repo(session: SessionDep) -> INotificationRepository:
    return NotificationRepository(session)


def get_notification_preference_repo(
    session: SessionDep,
) -> INotificationPreferenceRepository:
    return NotificationPreferenceRepository(session)


def get_notification_delivery_repo(session: SessionDep) -> INotificationDeliveryRepository:
    return NotificationDeliveryRepository(session)


def get_question_repo(session: SessionDep) -> IQuestionRepository:
    return QuestionRepositoryImpl(session)


def get_capability_question_repo(session: SessionDep) -> ICapabilityQuestionRepository:
    return SqlCapabilityQuestionRepository(session)


def get_capability_answer_repo(session: SessionDep) -> ICapabilityAnswerRepository:
    return SqlCapabilityAnswerRepository(session)


def get_capability_evidence_repo(session: SessionDep) -> ICapabilityEvidenceRepository:
    return SqlCapabilityEvidenceRepository(session)


def get_quotation_repo(session: SessionDep) -> IQuotationRepository:
    return QuotationRepository(session)


def get_tender_share_link_repo(session: SessionDep) -> ITenderShareLinkRepository:
    return TenderShareLinkRepository(session)


def get_export_job_repo(session: SessionDep) -> IExportJobRepository:
    return ExportJobRepository(session)


def get_proposal_draft_repo(session: SessionDep) -> IProposalDraftRepository:
    return SqlProposalDraftRepository(session)


def get_tender_chat_repo(session: SessionDep) -> ITenderChatRepository:
    return SQLTenderChatRepository(session)


def get_tender_milestone_repo(session: SessionDep) -> ITenderMilestoneRepository:
    return TenderMilestoneRepository(session)


def get_calendar_oauth_state_repo(session: SessionDep) -> ICalendarOAuthStateRepository:
    return CalendarOAuthStateRepository(session)


def get_calendar_event_link_repo(session: SessionDep) -> ICalendarEventLinkRepository:
    return CalendarEventLinkRepository(session)


def get_kanban_column_repo(session: SessionDep) -> IKanbanColumnRepository:
    return KanbanColumnRepository(session)


def get_kanban_card_repo(session: SessionDep) -> IKanbanCardRepository:
    return KanbanCardRepository(session)


SupplierRepoDep = Annotated[ISupplierRepository, Depends(get_supplier_repo)]
TenderRepoDep = Annotated[ITenderRepository, Depends(get_tender_repo)]
MatchingResultRepoDep = Annotated[
    IMatchingResultRepository, Depends(get_matching_result_repo)
]
SavedTenderRepoDep = Annotated[ISavedTenderRepository, Depends(get_saved_tender_repo)]
NotificationRepoDep = Annotated[INotificationRepository, Depends(get_notification_repo)]
NotificationPreferenceRepoDep = Annotated[
    INotificationPreferenceRepository, Depends(get_notification_preference_repo)
]
NotificationDeliveryRepoDep = Annotated[
    INotificationDeliveryRepository, Depends(get_notification_delivery_repo)
]
QuestionRepoDep = Annotated[IQuestionRepository, Depends(get_question_repo)]
CapabilityQuestionRepoDep = Annotated[
    ICapabilityQuestionRepository, Depends(get_capability_question_repo)
]
CapabilityAnswerRepoDep = Annotated[
    ICapabilityAnswerRepository, Depends(get_capability_answer_repo)
]
CapabilityEvidenceRepoDep = Annotated[
    ICapabilityEvidenceRepository, Depends(get_capability_evidence_repo)
]
QuotationRepoDep = Annotated[IQuotationRepository, Depends(get_quotation_repo)]
TenderShareLinkRepoDep = Annotated[
    ITenderShareLinkRepository, Depends(get_tender_share_link_repo)
]
ExportJobRepoDep = Annotated[IExportJobRepository, Depends(get_export_job_repo)]
ProposalDraftRepoDep = Annotated[IProposalDraftRepository, Depends(get_proposal_draft_repo)]
TenderChatRepoDep = Annotated[ITenderChatRepository, Depends(get_tender_chat_repo)]
TenderMilestoneRepoDep = Annotated[
    ITenderMilestoneRepository, Depends(get_tender_milestone_repo)
]
CalendarOAuthStateRepoDep = Annotated[
    ICalendarOAuthStateRepository, Depends(get_calendar_oauth_state_repo)
]
CalendarEventLinkRepoDep = Annotated[
    ICalendarEventLinkRepository, Depends(get_calendar_event_link_repo)
]
KanbanColumnRepoDep = Annotated[IKanbanColumnRepository, Depends(get_kanban_column_repo)]
KanbanCardRepoDep = Annotated[IKanbanCardRepository, Depends(get_kanban_card_repo)]


# --- Servicios y clientes construidos al arrancar (viven en app.state) ---


def get_supplier_vector_repo(request: Request) -> ISupplierVectorRepository:
    # Reutiliza el cliente Qdrant inicializado en el lifespan
    return QdrantSupplierRepository(request.app.state.qdrant_async_client)


def get_tender_vector_repo(request: Request) -> ITenderVectorRepository:
    return QdrantTenderRepository(
        client=request.app.state.qdrant_async_client,
        vector_size=settings.embedding_vector_size,
    )


def get_embedding_service(request: Request) -> IEmbeddingService:
    return request.app.state.embedding_service


def get_company_lookup_service(request: Request) -> ICompanyLookupService | None:
    # `None` cuando COMPANY_LOOKUP_PROVIDER=none: el caso de uso responde 503.
    return request.app.state.company_lookup_service


def get_reranker_service(request: Request) -> IRerankerService:
    return request.app.state.reranker_service


def get_weighting_service(request: Request) -> IWeightingService:
    return request.app.state.weighting_service


def get_email_service(request: Request) -> IEmailService:
    return request.app.state.email_service


def get_token_verifier(request: Request) -> IAuthTokenVerifier:
    """El verificador de tokens, como dependencia y no como objeto capturado.

    Que pase por el sistema de dependencias es lo que permite sustituirlo en los
    tests con `app.dependency_overrides`, y así ejercitar la verificación real
    contra un JWKS de prueba sin levantar Supabase.
    """
    return request.app.state.token_verifier


def get_identity_directory(session: SessionDep) -> IIdentityDirectory:
    return SupabaseIdentityDirectory(session)


def get_deep_analysis_service(request: Request) -> IDeepAnalysisService:
    return request.app.state.deep_analysis_service


def get_tender_assistant_ai_service(request: Request) -> ITenderAssistantAIService:
    return request.app.state.tender_assistant_ai_service


def get_milestone_extraction_service(request: Request) -> IMilestoneExtractionAIService:
    return request.app.state.milestone_extraction_service


def get_calendar_providers(request: Request) -> CalendarProviders:
    return request.app.state.calendar_providers


def get_token_cipher(request: Request) -> ITokenCipher:
    return request.app.state.token_cipher


def get_export_background(request: Request) -> IExportBackground:
    return request.app.state.export_background


def get_proposal_ai_service(request: Request) -> IProposalAIService:
    return request.app.state.proposal_ai_service


def get_document_validator_service() -> IDocumentValidatorService:
    return DocumentValidatorService()


SupplierVectorRepoDep = Annotated[
    ISupplierVectorRepository, Depends(get_supplier_vector_repo)
]
TenderVectorRepoDep = Annotated[ITenderVectorRepository, Depends(get_tender_vector_repo)]
EmbeddingServiceDep = Annotated[IEmbeddingService, Depends(get_embedding_service)]
CalendarProvidersDep = Annotated[CalendarProviders, Depends(get_calendar_providers)]
DocumentValidatorDep = Annotated[
    IDocumentValidatorService, Depends(get_document_validator_service)
]
ProposalAIServiceDep = Annotated[IProposalAIService, Depends(get_proposal_ai_service)]


def get_calendar_connection_repo(
    session: SessionDep,
    cipher: Annotated[ITokenCipher, Depends(get_token_cipher)],
) -> ICalendarConnectionRepository:
    return CalendarConnectionRepository(session, cipher)


CalendarConnectionRepoDep = Annotated[
    ICalendarConnectionRepository, Depends(get_calendar_connection_repo)
]


# --- Matching y licitaciones ---


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


# --- Licitaciones guardadas ---


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


# --- Capacidades y cotización ---


def get_build_experience_catalog_use_case(
    supplier_repo: SupplierRepoDep,
    question_repo: CapabilityQuestionRepoDep,
    answer_repo: CapabilityAnswerRepoDep,
    evidence_repo: CapabilityEvidenceRepoDep,
) -> BuildExperienceCatalogUseCase:
    return BuildExperienceCatalogUseCase(
        supplier_repo, question_repo, answer_repo, evidence_repo
    )


def get_answer_capability_question_use_case(
    supplier_repo: SupplierRepoDep,
    question_repo: CapabilityQuestionRepoDep,
    answer_repo: CapabilityAnswerRepoDep,
) -> AnswerCapabilityQuestionUseCase:
    return AnswerCapabilityQuestionUseCase(supplier_repo, question_repo, answer_repo)


def get_add_capability_evidence_use_case(
    supplier_repo: SupplierRepoDep,
    question_repo: CapabilityQuestionRepoDep,
    answer_repo: CapabilityAnswerRepoDep,
    evidence_repo: CapabilityEvidenceRepoDep,
) -> AddCapabilityEvidenceUseCase:
    return AddCapabilityEvidenceUseCase(
        supplier_repo, question_repo, answer_repo, evidence_repo
    )


def get_quotation_use_case(
    quotation_repo: QuotationRepoDep,
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
) -> QuotationUseCase:
    return QuotationUseCase(quotation_repo, supplier_repo, tender_repo)


CatalogUseCaseDep = Annotated[
    BuildExperienceCatalogUseCase, Depends(get_build_experience_catalog_use_case)
]
AnswerCapabilityUseCaseDep = Annotated[
    AnswerCapabilityQuestionUseCase, Depends(get_answer_capability_question_use_case)
]


# --- Postulaciones ---


def get_list_pending_capability_questions_use_case(
    supplier_repo: SupplierRepoDep,
    question_repo: CapabilityQuestionRepoDep,
    answer_repo: CapabilityAnswerRepoDep,
    tender_repo: TenderRepoDep,
) -> ListPendingCapabilityQuestionsUseCase:
    return ListPendingCapabilityQuestionsUseCase(
        supplier_repo, question_repo, answer_repo, tender_repo
    )


def get_start_feasibility_use_case(
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
    draft_repo: ProposalDraftRepoDep,
    question_repo: CapabilityQuestionRepoDep,
    answer_repo: CapabilityAnswerRepoDep,
    catalog_use_case: CatalogUseCaseDep,
    chat_repo: TenderChatRepoDep,
    ai_service: ProposalAIServiceDep,
    validator: DocumentValidatorDep,
) -> StartFeasibilityUseCase:
    return StartFeasibilityUseCase(
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        draft_repo=draft_repo,
        question_repo=question_repo,
        answer_repo=answer_repo,
        catalog_use_case=catalog_use_case,
        chat_repo=chat_repo,
        ai_service=ai_service,
        validator_service=validator,
    )


def get_proposal_use_case(
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
    draft_repo: ProposalDraftRepoDep,
    question_repo: CapabilityQuestionRepoDep,
    catalog_use_case: CatalogUseCaseDep,
) -> GetProposalUseCase:
    return GetProposalUseCase(
        supplier_repo, tender_repo, draft_repo, question_repo, catalog_use_case
    )


def get_answer_proposal_question_use_case(
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
    draft_repo: ProposalDraftRepoDep,
    question_repo: CapabilityQuestionRepoDep,
    answer_use_case: AnswerCapabilityUseCaseDep,
) -> AnswerProposalQuestionUseCase:
    return AnswerProposalQuestionUseCase(
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        draft_repo=draft_repo,
        question_repo=question_repo,
        answer_use_case=answer_use_case,
    )


def get_decide_discrepancy_use_case(
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
    draft_repo: ProposalDraftRepoDep,
) -> DecideDiscrepancyUseCase:
    return DecideDiscrepancyUseCase(supplier_repo, tender_repo, draft_repo)


def get_generate_proposal_use_case(
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
    draft_repo: ProposalDraftRepoDep,
    catalog_use_case: CatalogUseCaseDep,
    chat_repo: TenderChatRepoDep,
    ai_service: ProposalAIServiceDep,
    validator: DocumentValidatorDep,
) -> GenerateProposalUseCase:
    return GenerateProposalUseCase(
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        draft_repo=draft_repo,
        catalog_use_case=catalog_use_case,
        chat_repo=chat_repo,
        ai_service=ai_service,
        validator_service=validator,
    )


GenerateProposalUseCaseDep = Annotated[
    GenerateProposalUseCase, Depends(get_generate_proposal_use_case)
]


def get_regenerate_proposal_use_case(
    generate_use_case: GenerateProposalUseCaseDep,
) -> RegenerateProposalUseCase:
    return RegenerateProposalUseCase(generate_use_case)


def get_sync_proposal_answers_use_case(
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
    draft_repo: ProposalDraftRepoDep,
    catalog_use_case: CatalogUseCaseDep,
    generate_use_case: GenerateProposalUseCaseDep,
) -> SyncProposalAnswersUseCase:
    return SyncProposalAnswersUseCase(
        supplier_repo, tender_repo, draft_repo, catalog_use_case, generate_use_case
    )


def get_export_proposal_use_case(
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
    draft_repo: ProposalDraftRepoDep,
) -> ExportProposalDocxUseCase:
    return ExportProposalDocxUseCase(
        supplier_repo, tender_repo, draft_repo, DocxProposalExporter()
    )


def get_resume_proposal_use_case(
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
    draft_repo: ProposalDraftRepoDep,
) -> ResumeProposalUseCase:
    return ResumeProposalUseCase(supplier_repo, tender_repo, draft_repo)


# --- Exportaciones y enlaces compartidos (HdU 19) ---


def get_export_tender_use_case(
    tenders: TenderRepoDep,
    matching_results: MatchingResultRepoDep,
    quotations: QuotationRepoDep,
    jobs: ExportJobRepoDep,
    background: Annotated[IExportBackground, Depends(get_export_background)],
) -> ExportTenderUseCase:
    return ExportTenderUseCase(
        snapshots=BuildExportSnapshotUseCase(
            tenders=tenders, matching_results=matching_results, quotations=quotations
        ),
        jobs=jobs,
        pdf_renderer=ReportLabPdfRenderer(),
        excel_renderer=OpenpyxlExcelRenderer(),
        background=background,
        inline_timeout_seconds=settings.export_inline_timeout_seconds,
    )


def get_export_job_use_case(jobs: ExportJobRepoDep) -> GetExportJobUseCase:
    return GetExportJobUseCase(jobs)


def get_download_export_file_use_case(
    jobs: ExportJobRepoDep,
) -> DownloadExportFileUseCase:
    return DownloadExportFileUseCase(jobs)


def build_export_background(app: FastAPI) -> AsyncioExportBackground:
    """Termina las exportaciones que pasaron a segundo plano.

    Cada trabajo abre su propia sesión: cuando la generación termina, la sesión
    de la petición que lo originó ya se cerró.
    """

    @asynccontextmanager
    async def open_completion():
        async with async_session_maker() as session:
            yield CompleteExportJobUseCase(
                jobs=ExportJobRepository(session),
                email=app.state.email_service,
                base_url=settings.app_base_url,
            )

    return AsyncioExportBackground(open_completion)


async def reconcile_export_jobs() -> tuple[int, int]:
    """Al arrancar: falla lo que quedó en proceso y vacía los archivos vencidos."""
    async with async_session_maker() as session:
        return await ReconcileExportJobsUseCase(ExportJobRepository(session)).execute()


def get_create_share_link_use_case(
    links: TenderShareLinkRepoDep,
    tenders: TenderRepoDep,
) -> CreateShareLinkUseCase:
    return CreateShareLinkUseCase(links=links, tenders=tenders, base_url=settings.app_base_url)


def get_list_share_links_use_case(links: TenderShareLinkRepoDep) -> ListShareLinksUseCase:
    return ListShareLinksUseCase(links=links)


def get_revoke_share_link_use_case(links: TenderShareLinkRepoDep) -> RevokeShareLinkUseCase:
    return RevokeShareLinkUseCase(links=links)


def get_shared_tender_use_case(
    links: TenderShareLinkRepoDep,
    tenders: TenderRepoDep,
    suppliers: SupplierRepoDep,
    matching_results: MatchingResultRepoDep,
) -> GetSharedTenderUseCase:
    return GetSharedTenderUseCase(
        links=links,
        tenders=tenders,
        suppliers=suppliers,
        matching_results=matching_results,
    )


# --- Alertas de licitaciones (HdU 08) ---


def get_list_notifications_use_case(
    notification_repo: NotificationRepoDep,
    tender_repo: TenderRepoDep,
) -> ListNotificationsUseCase:
    return ListNotificationsUseCase(
        notification_repo=notification_repo,
        tender_repo=tender_repo,
    )


def get_count_unread_use_case(
    notification_repo: NotificationRepoDep,
) -> CountUnreadNotificationsUseCase:
    return CountUnreadNotificationsUseCase(notification_repo=notification_repo)


def get_mark_notification_read_use_case(
    notification_repo: NotificationRepoDep,
) -> MarkNotificationReadUseCase:
    return MarkNotificationReadUseCase(notification_repo=notification_repo)


def get_mark_all_read_use_case(
    notification_repo: NotificationRepoDep,
) -> MarkAllNotificationsReadUseCase:
    return MarkAllNotificationsReadUseCase(notification_repo=notification_repo)


def get_notification_preferences_use_case(
    preference_repo: NotificationPreferenceRepoDep,
) -> GetNotificationPreferencesUseCase:
    return GetNotificationPreferencesUseCase(preference_repo=preference_repo)


def get_update_notification_preferences_use_case(
    preference_repo: NotificationPreferenceRepoDep,
) -> UpdateNotificationPreferencesUseCase:
    return UpdateNotificationPreferencesUseCase(preference_repo=preference_repo)


def get_list_deliveries_use_case(
    delivery_repo: NotificationDeliveryRepoDep,
) -> ListDeliveriesUseCase:
    return ListDeliveriesUseCase(delivery_repo=delivery_repo)


# --- Preguntas inteligentes ---


def get_smart_question_service(question_repo: QuestionRepoDep) -> ISmartQuestionService:
    return SmartQuestionServiceImpl(question_repository=question_repo)


def get_smart_question_use_case(
    smart_question_service: Annotated[
        ISmartQuestionService, Depends(get_smart_question_service)
    ],
    supplier_repo: SupplierRepoDep,
) -> SmartQuestionUseCase:
    return SmartQuestionUseCase(
        smart_question_service=smart_question_service,
        supplier_repository=supplier_repo,
    )


def get_answer_question_use_case(supplier_repo: SupplierRepoDep) -> AnswerQuestionUseCase:
    # Inyectar el caso de uso que procesa las respuestas
    return AnswerQuestionUseCase(supplier_repo=supplier_repo)


# --- Calendario e hitos (HU-16) ---


def get_calendar_connections_use_case(
    connections: CalendarConnectionRepoDep,
    providers: CalendarProvidersDep,
) -> GetCalendarConnectionsUseCase:
    return GetCalendarConnectionsUseCase(connections, providers)


def get_start_calendar_authorization_use_case(
    milestones: TenderMilestoneRepoDep,
    states: CalendarOAuthStateRepoDep,
    providers: CalendarProvidersDep,
) -> StartCalendarAuthorizationUseCase:
    return StartCalendarAuthorizationUseCase(
        milestones=milestones,
        states=states,
        providers=providers,
    )


def get_complete_calendar_authorization_use_case(
    states: CalendarOAuthStateRepoDep,
    connections: CalendarConnectionRepoDep,
    providers: CalendarProvidersDep,
) -> CompleteCalendarAuthorizationUseCase:
    return CompleteCalendarAuthorizationUseCase(
        states=states,
        connections=connections,
        providers=providers,
    )


def get_sync_milestones_use_case(
    tenders: TenderRepoDep,
    milestones: TenderMilestoneRepoDep,
    connections: CalendarConnectionRepoDep,
    event_links: CalendarEventLinkRepoDep,
    providers: CalendarProvidersDep,
) -> SyncMilestonesToCalendarUseCase:
    return SyncMilestonesToCalendarUseCase(
        tenders=tenders,
        milestones=milestones,
        connections=connections,
        event_links=event_links,
        providers=providers,
        app_base_url=settings.app_base_url,
    )


def get_disconnect_calendar_use_case(
    connections: CalendarConnectionRepoDep,
    providers: CalendarProvidersDep,
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
    tenders: TenderRepoDep,
    milestones: TenderMilestoneRepoDep,
    event_links: CalendarEventLinkRepoDep,
    chat: TenderChatRepoDep,
) -> GetTenderMilestonesUseCase:
    return GetTenderMilestonesUseCase(
        tenders=tenders,
        milestones=milestones,
        event_links=event_links,
        chat=chat,
    )


def get_set_milestone_reminder_use_case(
    milestones: TenderMilestoneRepoDep,
) -> SetMilestoneReminderUseCase:
    return SetMilestoneReminderUseCase(milestones)


def get_extract_tender_milestones_use_case(
    tenders: TenderRepoDep,
    milestones: TenderMilestoneRepoDep,
    event_links: CalendarEventLinkRepoDep,
    chat: TenderChatRepoDep,
    ai: Annotated[IMilestoneExtractionAIService, Depends(get_milestone_extraction_service)],
) -> ExtractTenderMilestonesUseCase:
    return ExtractTenderMilestonesUseCase(
        tenders=tenders,
        milestones=milestones,
        event_links=event_links,
        chat=chat,
        ai=ai,
    )


# --- Asistente de licitaciones ---


def get_upload_tender_chat_doc_use_case(
    chat_repo: TenderChatRepoDep,
    validator_service: DocumentValidatorDep,
) -> UploadTenderChatDocumentUseCase:
    return UploadTenderChatDocumentUseCase(
        chat_repo=chat_repo, validator_service=validator_service
    )


def get_list_tender_chat_docs_use_case(
    chat_repo: TenderChatRepoDep,
) -> ListTenderChatDocumentsUseCase:
    return ListTenderChatDocumentsUseCase(chat_repo=chat_repo)


def get_delete_tender_chat_doc_use_case(
    chat_repo: TenderChatRepoDep,
) -> DeleteTenderChatDocumentUseCase:
    return DeleteTenderChatDocumentUseCase(chat_repo=chat_repo)


def get_ask_tender_assistant_use_case(
    chat_repo: TenderChatRepoDep,
    ai_service: Annotated[
        ITenderAssistantAIService, Depends(get_tender_assistant_ai_service)
    ],
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
    validator_service: DocumentValidatorDep,
) -> AskTenderAssistantUseCase:
    return AskTenderAssistantUseCase(
        chat_repo=chat_repo,
        ai_service=ai_service,
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        validator_service=validator_service,
    )


def get_create_tender_chat_session_use_case(
    chat_repo: TenderChatRepoDep,
) -> CreateTenderChatSessionUseCase:
    return CreateTenderChatSessionUseCase(chat_repo=chat_repo)


def get_tender_chat_history_use_case(
    chat_repo: TenderChatRepoDep,
) -> GetTenderChatHistoryUseCase:
    return GetTenderChatHistoryUseCase(chat_repo=chat_repo)


# --- Tablero Kanban (HdU 10) ---


def get_list_kanban_columns_use_case(
    column_repo: KanbanColumnRepoDep,
) -> ListKanbanColumnsUseCase:
    return ListKanbanColumnsUseCase(column_repo=column_repo)


def get_create_kanban_column_use_case(
    column_repo: KanbanColumnRepoDep,
) -> CreateKanbanColumnUseCase:
    return CreateKanbanColumnUseCase(column_repo=column_repo)


def get_update_kanban_column_use_case(
    column_repo: KanbanColumnRepoDep,
) -> UpdateKanbanColumnUseCase:
    return UpdateKanbanColumnUseCase(column_repo=column_repo)


def get_delete_kanban_column_use_case(
    column_repo: KanbanColumnRepoDep,
) -> DeleteKanbanColumnUseCase:
    return DeleteKanbanColumnUseCase(column_repo=column_repo)


def get_list_kanban_cards_use_case(card_repo: KanbanCardRepoDep) -> ListKanbanCardsUseCase:
    return ListKanbanCardsUseCase(card_repo=card_repo)


def get_add_tender_to_board_use_case(
    card_repo: KanbanCardRepoDep,
    column_repo: KanbanColumnRepoDep,
) -> AddTenderToBoardUseCase:
    return AddTenderToBoardUseCase(card_repo=card_repo, column_repo=column_repo)


def get_move_kanban_card_use_case(
    card_repo: KanbanCardRepoDep,
    column_repo: KanbanColumnRepoDep,
) -> MoveKanbanCardUseCase:
    return MoveKanbanCardUseCase(card_repo=card_repo, column_repo=column_repo)


def get_remove_tender_from_board_use_case(
    card_repo: KanbanCardRepoDep,
) -> RemoveTenderFromBoardUseCase:
    return RemoveTenderFromBoardUseCase(card_repo=card_repo)


class MockRerankerService(IRerankerService):
    """Reranker neutro para cuando está desactivado o falta ONNX en local/tests."""

    async def rerank(self, query_text, candidates, limit):
        return [(c[0], 1.0) for c in candidates][:limit]


logger = logging.getLogger(__name__)


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
                weighting_service=app.state.weighting_service,
                matching_result_repo=MatchingResultRepository(session),
                model_version=settings.embedding_model,
            ),
            matching_result_repo=MatchingResultRepository(session),
            model_version=settings.embedding_model,
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
    app.state.proposal_ai_service = GeminiProposalService(
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

    app.state.export_background = build_export_background(app)

    # La región no pondera: `RankTendersUseCase` ya descarta las licitaciones
    # fuera de las regiones del proveedor, así que un bono adicional se lo
    # llevarían todas las que sobreviven al filtro y no ordenaría nada.
    # Estos son los pesos con que se calibró el reranker en
    # tests/matching_evaluation.
    app.state.weighting_service = FieldWeightingService(
        reranker_weight=0.50,
        sector_weight=0.25,
        keyword_weight=0.25,
        region_weight=0.0,
    )

    # Importación tardía y transitoria: routes.py importa los providers de este
    # módulo, que todavía viven acá. Se mueve arriba al separar los providers.
    from app.bootstrap.routes import register_routes

    register_routes(app)
