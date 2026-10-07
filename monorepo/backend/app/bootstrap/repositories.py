"""Repositorios SQL por petición y sus alias `Annotated` (`*RepoDep`)."""

from typing import Annotated

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.calendar_repository import (
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
from app.application.repositories.milestone_document_repository import (
    IMilestoneDocumentRepository,
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
from app.application.repositories.tender_chat_repository import ITenderChatRepository
from app.application.repositories.tender_milestone_repository import (
    ITenderMilestoneRepository,
)
from app.application.repositories.tender_repository import ITenderRepository
from app.application.repositories.tender_share_link_repository import (
    ITenderShareLinkRepository,
)
from app.application.repositories.user_repository import IUserRepository
from app.infrastructure.db import get_session
from app.infrastructure.repositories.calendar_repository import (
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
from app.infrastructure.repositories.tender_milestone_document_repository import (
    TenderMilestoneDocumentRepository,
)
from app.infrastructure.repositories.tender_milestone_repository import (
    TenderMilestoneRepository,
)
from app.infrastructure.repositories.tender_repository import TenderRepository
from app.infrastructure.repositories.tender_share_link_repository import (
    TenderShareLinkRepository,
)
from app.infrastructure.repositories.user_repository import UserRepository

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


def get_milestone_document_repo(session: SessionDep) -> IMilestoneDocumentRepository:
    return TenderMilestoneDocumentRepository(session)


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
MilestoneDocumentRepoDep = Annotated[
    IMilestoneDocumentRepository, Depends(get_milestone_document_repo)
]


CalendarOAuthStateRepoDep = Annotated[
    ICalendarOAuthStateRepository, Depends(get_calendar_oauth_state_repo)
]


CalendarEventLinkRepoDep = Annotated[
    ICalendarEventLinkRepository, Depends(get_calendar_event_link_repo)
]


KanbanColumnRepoDep = Annotated[IKanbanColumnRepository, Depends(get_kanban_column_repo)]


KanbanCardRepoDep = Annotated[IKanbanCardRepository, Depends(get_kanban_card_repo)]
