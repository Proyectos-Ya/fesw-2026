"""Punto único de registro de los modelos de base de datos.

SQLModel solo agrega una tabla a `SQLModel.metadata` cuando su módulo se importa.
Alembic necesita ese metadata completo para `--autogenerate`: si falta un módulo,
no ve la tabla y genera una migración que la **borra**.

Importar desde acá evita que eso dependa de qué módulos haya cargado la
aplicación por casualidad. Al agregar un modelo nuevo, agregarlo también aquí.
"""

from app.infrastructure.repositories.attachment_file_model import (
    AttachmentFileModel,
    AttachmentUploadQuotaModel,
)
from app.infrastructure.repositories.attachment_processing_model import (
    AttachmentExtractionModel,
    AttachmentGeminiDailyUsageModel,
    AttachmentProcessingJobModel,
    TenderDigestModel,
)
from app.infrastructure.repositories.calendar_model import (
    CalendarConnectionModel,
    CalendarEventLinkModel,
    CalendarOAuthStateModel,
)
from app.infrastructure.repositories.capability_model import (
    CapabilityAnswerModel,
    CapabilityEvidenceModel,
    CapabilityQuestionModel,
)
from app.infrastructure.repositories.deep_analysis_model import (
    DeepAnalysisModel,
)
from app.infrastructure.repositories.export_job_model import ExportJobModel
from app.infrastructure.repositories.extension_model import (
    ExtensionFetchJobModel,
    ExtensionInstallationModel,
)
from app.infrastructure.repositories.kanban_model import (
    KanbanCardModel,
    KanbanColumnModel,
)
from app.infrastructure.repositories.matching_result_model import (
    MatchingResultModel,
)
from app.infrastructure.repositories.matching_shadow_model import (
    MatchingShadowScoreModel,
    TenderAttachmentItemModel,
)
from app.infrastructure.repositories.notification_model import (
    NotificationDeliveryModel,
    NotificationModel,
    NotificationPreferenceModel,
)
from app.infrastructure.repositories.proposal_model import ProposalDraftModel
from app.infrastructure.repositories.question_model import QuestionModel
from app.infrastructure.repositories.quotation_model import (
    QuotationMaterialModel,
    QuotationModel,
)
from app.infrastructure.repositories.ranking_telemetry_model import (
    AttachmentPriorityShadowModel,
    RankingImpressionModel,
    RankingMetricDailyModel,
    TenderInteractionModel,
)
from app.infrastructure.repositories.saved_tender_model import SavedTenderModel
from app.infrastructure.repositories.supplier_invitation_model import (
    SupplierInvitationModel,
)
from app.infrastructure.repositories.supplier_member_model import (
    SupplierMemberModel,
)
from app.infrastructure.repositories.supplier_model import SupplierModel
from app.infrastructure.repositories.sync_estados_run_model import (
    SyncEstadosRunModel,
)
from app.infrastructure.repositories.tender_attachment_model import (
    TenderAttachmentModel,
)
from app.infrastructure.repositories.tender_chat_model import (
    TenderChatDocumentModel,
    TenderChatMessageModel,
    TenderChatSessionModel,
)
from app.infrastructure.repositories.tender_milestone_attachment_model import (
    TenderMilestoneAttachmentModel,
)
from app.infrastructure.repositories.tender_milestone_document_model import (
    TenderMilestoneDocumentModel,
)
from app.infrastructure.repositories.tender_milestone_model import (
    TenderMilestoneModel,
)
from app.infrastructure.repositories.tender_model import (
    BuyerInstitutionModel,
    RegionModel,
    TenderAIAnalysisModel,
    TenderItemModel,
    TenderMetadataModel,
    TenderModel,
    TenderStatusModel,
)
from app.infrastructure.repositories.tender_share_link_model import (
    TenderShareLinkModel,
)
from app.infrastructure.repositories.user_model import UserModel

__all__ = [
    "AttachmentExtractionModel",
    "AttachmentFileModel",
    "AttachmentGeminiDailyUsageModel",
    "AttachmentPriorityShadowModel",
    "AttachmentProcessingJobModel",
    "AttachmentUploadQuotaModel",
    "SyncEstadosRunModel",
    "CapabilityAnswerModel",
    "CapabilityEvidenceModel",
    "CapabilityQuestionModel",
    "CalendarConnectionModel",
    "CalendarEventLinkModel",
    "CalendarOAuthStateModel",
    "ExtensionFetchJobModel",
    "ExtensionInstallationModel",
    "TenderMilestoneModel",
    "TenderMilestoneAttachmentModel",
    "TenderMilestoneDocumentModel",
    "QuotationModel",
    "QuotationMaterialModel",
    "BuyerInstitutionModel",
    "DeepAnalysisModel",
    "ExportJobModel",
    "KanbanCardModel",
    "KanbanColumnModel",
    "MatchingResultModel",
    "MatchingShadowScoreModel",
    "NotificationDeliveryModel",
    "NotificationModel",
    "NotificationPreferenceModel",
    "ProposalDraftModel",
    "QuestionModel",
    "RankingImpressionModel",
    "RankingMetricDailyModel",
    "RegionModel",
    "SavedTenderModel",
    "SupplierModel",
    "SupplierMemberModel",
    "SupplierInvitationModel",
    "TenderAIAnalysisModel",
    "TenderAttachmentItemModel",
    "TenderAttachmentModel",
    "TenderItemModel",
    "TenderMetadataModel",
    "TenderModel",
    "TenderStatusModel",
    "TenderChatDocumentModel",
    "TenderChatMessageModel",
    "TenderChatSessionModel",
    "TenderDigestModel",
    "TenderInteractionModel",
    "TenderShareLinkModel",
    "UserModel",
]
