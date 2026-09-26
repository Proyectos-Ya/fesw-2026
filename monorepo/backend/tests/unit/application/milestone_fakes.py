"""Dobles en memoria para los casos de uso de hitos y calendario (HU-16)."""

from datetime import datetime
from uuid import UUID

from app.application.repositories.calendar_repository import (
    ICalendarConnectionRepository,
    ICalendarEventLinkRepository,
    ICalendarOAuthStateRepository,
)
from app.application.repositories.tender_milestone_repository import (
    ITenderMilestoneRepository,
)
from app.application.services.calendar_provider_client import (
    ICalendarProviderClient,
    OAuthTokens,
)
from app.application.services.milestone_extraction_ai_service import (
    ExtractedMilestone,
    IMilestoneExtractionAIService,
)
from app.application.services.tender_assistant_ai_service import DocumentContextDTO
from app.domain.entities.calendar import (
    CalendarConnection,
    CalendarEventLink,
    CalendarOAuthState,
    CalendarProvider,
)
from app.domain.entities.tender_milestone import TenderMilestone
from app.domain.errors.milestone_errors import MilestoneExtractionUnavailable


class InMemoryTenderMilestoneRepository(ITenderMilestoneRepository):
    def __init__(self) -> None:
        self.items: dict[UUID, TenderMilestone] = {}

    async def list_for_tender(self, user_id: UUID, tender_id: UUID) -> list[TenderMilestone]:
        return sorted(
            (m for m in self.items.values() if m.user_id == user_id and m.tender_id == tender_id),
            key=lambda m: m.due_at,
        )

    async def list_by_ids(self, user_id: UUID, milestone_ids: list[UUID]) -> list[TenderMilestone]:
        return sorted(
            (m for m in self.items.values() if m.user_id == user_id and m.id in milestone_ids),
            key=lambda m: m.due_at,
        )

    async def save_many(self, milestones: list[TenderMilestone]) -> None:
        for milestone in milestones:
            self.items[milestone.id] = milestone

    async def delete_many(self, user_id: UUID, milestone_ids: list[UUID]) -> None:
        for milestone_id in milestone_ids:
            if milestone_id in self.items and self.items[milestone_id].user_id == user_id:
                del self.items[milestone_id]


class InMemoryCalendarEventLinkRepository(ICalendarEventLinkRepository):
    def __init__(self) -> None:
        self.items: dict[tuple[UUID, CalendarProvider], CalendarEventLink] = {}

    async def list_by_milestones(
        self, milestone_ids: list[UUID], provider: CalendarProvider
    ) -> list[CalendarEventLink]:
        return [
            link for (milestone_id, p), link in self.items.items()
            if milestone_id in milestone_ids and p is provider
        ]

    async def save(self, link: CalendarEventLink) -> None:
        self.items[(link.milestone_id, link.provider)] = link


class FakeMilestoneExtractionAIService(IMilestoneExtractionAIService):
    def __init__(self, hitos: list[ExtractedMilestone] | None = None, falla: bool = False) -> None:
        self.hitos = hitos or []
        self.falla = falla
        self.llamadas: list[tuple[list[DocumentContextDTO], str]] = []

    async def extract(
        self, documents: list[DocumentContextDTO], tender_context: str
    ) -> list[ExtractedMilestone]:
        self.llamadas.append((documents, tender_context))
        if self.falla:
            raise MilestoneExtractionUnavailable()
        return self.hitos


class InMemoryCalendarConnectionRepository(ICalendarConnectionRepository):
    def __init__(self) -> None:
        self.items: dict[tuple[UUID, CalendarProvider], CalendarConnection] = {}

    async def get(self, user_id: UUID, provider: CalendarProvider) -> CalendarConnection | None:
        return self.items.get((user_id, provider))

    async def save(self, connection: CalendarConnection) -> None:
        self.items[(connection.user_id, connection.provider)] = connection

    async def delete(self, user_id: UUID, provider: CalendarProvider) -> None:
        self.items.pop((user_id, provider), None)


class InMemoryCalendarOAuthStateRepository(ICalendarOAuthStateRepository):
    def __init__(self) -> None:
        self.items: dict[str, CalendarOAuthState] = {}

    async def save(self, state: CalendarOAuthState) -> None:
        self.items[state.state_hash] = state

    async def consume(self, state_hash: str) -> CalendarOAuthState | None:
        return self.items.pop(state_hash, None)


class FakeCalendarProviderClient(ICalendarProviderClient):
    def __init__(self) -> None:
        self.tokens = OAuthTokens(
            access_token="ya29.acceso",
            refresh_token="1//refresco",
            expires_at=datetime(2030, 1, 1),
            account_email="usuario@gmail.com",
        )
        self.urls_pedidas: list[str] = []
        self.codigos: list[str] = []
        self.refrescos: list[str] = []
        self.revocados: list[str] = []

    def authorization_url(self, state: str) -> str:
        self.urls_pedidas.append(state)
        return f"https://proveedor.test/auth?state={state}"

    async def exchange_code(self, code: str) -> OAuthTokens:
        self.codigos.append(code)
        return self.tokens

    async def refresh(self, refresh_token: str) -> OAuthTokens:
        self.refrescos.append(refresh_token)
        return self.tokens

    async def revoke(self, token: str) -> None:
        self.revocados.append(token)
