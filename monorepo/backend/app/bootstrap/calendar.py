"""Providers de calendario e hitos (HU-16)."""

from typing import Annotated

from fastapi import Depends

from app.application.repositories.calendar_repository import (
    ICalendarConnectionRepository,
    ICalendarEventLinkRepository,
)
from app.application.repositories.tender_milestone_repository import (
    ITenderMilestoneRepository,
)
from app.application.repositories.tender_repository import ITenderRepository
from app.application.services.calendar_provider_client import CalendarProviders
from app.application.services.milestone_extraction_ai_service import (
    IMilestoneExtractionAIService,
)
from app.application.services.token_cipher import ITokenCipher
from app.application.use_cases.calendar.calendar_authorization import (
    CompleteCalendarAuthorizationUseCase,
    StartCalendarAuthorizationUseCase,
)
from app.application.use_cases.calendar.calendar_connections import (
    DisconnectCalendarUseCase,
    GetCalendarConnectionsUseCase,
)
from app.application.use_cases.calendar.sync_milestones import (
    SyncMilestonesToCalendarUseCase,
)
from app.application.use_cases.milestones.extract_tender_milestones import (
    ExtractTenderMilestonesUseCase,
)
from app.application.use_cases.milestones.get_tender_milestones import (
    GetTenderMilestonesUseCase,
)
from app.application.use_cases.milestones.set_milestone_reminder import (
    SetMilestoneReminderUseCase,
)
from app.bootstrap.repositories import (
    CalendarEventLinkRepoDep,
    CalendarOAuthStateRepoDep,
    MilestoneDocumentRepoDep,
    SessionDep,
    TenderChatRepoDep,
    TenderMilestoneRepoDep,
    TenderRepoDep,
)
from app.bootstrap.services import (
    CalendarProvidersDep,
    MilestoneExtractionBackgroundDep,
    get_milestone_extraction_service,
    get_token_cipher,
)
from app.config import settings
from app.infrastructure.repositories.calendar_repository import (
    CalendarConnectionRepository,
)


def get_calendar_connection_repo(
    session: SessionDep,
    cipher: Annotated[ITokenCipher, Depends(get_token_cipher)],
) -> ICalendarConnectionRepository:
    return CalendarConnectionRepository(session, cipher)


CalendarConnectionRepoDep = Annotated[
    ICalendarConnectionRepository, Depends(get_calendar_connection_repo)
]


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


def build_sync_milestones_use_case(
    *,
    tenders: ITenderRepository,
    milestones: ITenderMilestoneRepository,
    connections: ICalendarConnectionRepository,
    event_links: ICalendarEventLinkRepository,
    providers: CalendarProviders,
) -> SyncMilestonesToCalendarUseCase:
    """Compartido por el provider de la API y el refresco de hitos del scheduler.

    Argumentos obligatorios y por nombre, por la misma razón que en
    `matching.build_rank_tenders_use_case`.
    """
    return SyncMilestonesToCalendarUseCase(
        tenders=tenders,
        milestones=milestones,
        connections=connections,
        event_links=event_links,
        providers=providers,
        app_base_url=settings.app_base_url,
    )


def get_sync_milestones_use_case(
    tenders: TenderRepoDep,
    milestones: TenderMilestoneRepoDep,
    connections: CalendarConnectionRepoDep,
    event_links: CalendarEventLinkRepoDep,
    providers: CalendarProvidersDep,
) -> SyncMilestonesToCalendarUseCase:
    return build_sync_milestones_use_case(
        tenders=tenders,
        milestones=milestones,
        connections=connections,
        event_links=event_links,
        providers=providers,
    )


def get_disconnect_calendar_use_case(
    connections: CalendarConnectionRepoDep,
    providers: CalendarProvidersDep,
) -> DisconnectCalendarUseCase:
    return DisconnectCalendarUseCase(connections, providers)


def get_tender_milestones_use_case(
    tenders: TenderRepoDep,
    milestones: TenderMilestoneRepoDep,
    event_links: CalendarEventLinkRepoDep,
    chat: TenderChatRepoDep,
    processed: MilestoneDocumentRepoDep,
    extraction: MilestoneExtractionBackgroundDep,
) -> GetTenderMilestonesUseCase:
    return GetTenderMilestonesUseCase(
        tenders=tenders,
        milestones=milestones,
        event_links=event_links,
        chat=chat,
        processed=processed,
        extraction=extraction,
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
    processed: MilestoneDocumentRepoDep,
    ai: Annotated[IMilestoneExtractionAIService, Depends(get_milestone_extraction_service)],
) -> ExtractTenderMilestonesUseCase:
    return ExtractTenderMilestonesUseCase(
        tenders=tenders,
        milestones=milestones,
        event_links=event_links,
        chat=chat,
        ai=ai,
        processed=processed,
    )
