"""Dobles en memoria para los casos de uso de hitos y calendario (HU-16)."""

from datetime import datetime
from uuid import UUID

from app.application.repositories.calendar_repository import (
    ICalendarConnectionRepository,
    ICalendarEventLinkRepository,
    ICalendarOAuthStateRepository,
)
from app.application.repositories.milestone_document_repository import (
    IMilestoneDocumentRepository,
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
    CalendarEventDraft,
    CalendarEventLink,
    CalendarOAuthState,
    CalendarProvider,
)
from app.domain.entities.tender_milestone import MilestoneSource, TenderMilestone
from app.domain.errors.calendar_errors import (
    CalendarAuthExpired,
    CalendarEventNotFound,
    CalendarProviderUnavailable,
)
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

    async def list_by_tender_and_source(
        self, tender_id: UUID, source: MilestoneSource
    ) -> list[TenderMilestone]:
        return [m for m in self.items.values() if m.tender_id == tender_id and m.source is source]

    async def list_pending_reminders(self, now: datetime) -> list[TenderMilestone]:
        return [m for m in self.items.values() if m.recordatorio_pendiente(now)]

    async def set_reminder(
        self, user_id: UUID, milestone_id: UUID, days_before: int | None
    ) -> TenderMilestone | None:
        hito = self.items.get(milestone_id)
        if hito is None or hito.user_id != user_id:
            return None
        actualizado = hito.model_copy(
            update={"reminder_days_before": days_before, "reminder_sent_at": None}
        )
        self.items[milestone_id] = actualizado
        return actualizado


class InMemoryCalendarEventLinkRepository(ICalendarEventLinkRepository):
    def __init__(self, milestones: InMemoryTenderMilestoneRepository | None = None) -> None:
        self.items: dict[tuple[UUID, CalendarProvider], CalendarEventLink] = {}
        # Los enlaces no guardan la licitación: se llega a ella por el hito.
        self._milestones = milestones or InMemoryTenderMilestoneRepository()

    def _tender_de(self, link: CalendarEventLink) -> UUID | None:
        hito = self._milestones.items.get(link.milestone_id)
        return hito.tender_id if hito else None

    async def list_linked_tender_ids(self) -> list[UUID]:
        return list({t for link in self.items.values() if (t := self._tender_de(link))})

    async def list_by_tender(self, tender_id: UUID) -> list[CalendarEventLink]:
        return [link for link in self.items.values() if self._tender_de(link) == tender_id]

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
    """Devuelve `hitos`, o lo de `por_documento` si la llamada trae ese archivo.

    `fallan` lista los nombres de archivo con los que la IA no responde.
    """

    def __init__(
        self,
        hitos: list[ExtractedMilestone] | None = None,
        falla: bool = False,
        por_documento: dict[str, list[ExtractedMilestone]] | None = None,
        fallan: set[str] | None = None,
    ) -> None:
        self.hitos = hitos or []
        self.falla = falla
        self.por_documento = por_documento or {}
        self.fallan = fallan or set()
        self.llamadas: list[tuple[list[DocumentContextDTO], str]] = []

    async def extract(
        self, documents: list[DocumentContextDTO], tender_context: str
    ) -> list[ExtractedMilestone]:
        self.llamadas.append((documents, tender_context))
        nombres = {d.document_name for d in documents}
        if self.falla or nombres & self.fallan:
            raise MilestoneExtractionUnavailable()
        for nombre in nombres:
            if nombre in self.por_documento:
                return self.por_documento[nombre]
        return self.hitos


class InMemoryMilestoneDocumentRepository(IMilestoneDocumentRepository):
    def __init__(self) -> None:
        self.items: dict[UUID, tuple[UUID, UUID, int]] = {}  # documento: (usuario, licitación, hitos)

    async def list_processed(self, user_id: UUID, tender_id: UUID) -> set[UUID]:
        return {d for d, (u, t, _) in self.items.items() if u == user_id and t == tender_id}

    async def mark_processed(
        self,
        user_id: UUID,
        tender_id: UUID,
        document_id: UUID,
        milestones_found: int,
        now: datetime,
    ) -> None:
        self.items[document_id] = (user_id, tender_id, milestones_found)


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
        self.eventos: dict[str, CalendarEventDraft] = {}
        self.actualizados: list[str] = []
        self.tokens_usados: list[str] = []
        self.fallar_en: set[UUID] = set()
        self.refresh_revocado = False
        # Token que Google rechaza con 401 aunque todavía no haya vencido.
        self.rechazar_token: str | None = None
        self._creados = 0

    def authorization_url(self, state: str) -> str:
        self.urls_pedidas.append(state)
        return f"https://proveedor.test/auth?state={state}"

    async def exchange_code(self, code: str) -> OAuthTokens:
        self.codigos.append(code)
        return self.tokens

    async def refresh(self, refresh_token: str) -> OAuthTokens:
        self.refrescos.append(refresh_token)
        if self.refresh_revocado:
            raise CalendarAuthExpired()
        return self.tokens

    async def revoke(self, token: str) -> None:
        self.revocados.append(token)

    def _verificar(self, access_token: str, draft: CalendarEventDraft) -> None:
        if access_token == self.rechazar_token:
            raise CalendarAuthExpired()
        if draft.milestone_id in self.fallar_en:
            raise CalendarProviderUnavailable()
        self.tokens_usados.append(access_token)

    async def create_event(self, access_token: str, draft: CalendarEventDraft) -> str:
        self._verificar(access_token, draft)
        self._creados += 1
        evento_id = f"evento-{self._creados}"
        self.eventos[evento_id] = draft
        return evento_id

    async def update_event(self, access_token: str, event_id: str, draft: CalendarEventDraft) -> None:
        self._verificar(access_token, draft)
        if event_id not in self.eventos:
            raise CalendarEventNotFound()
        self.eventos[event_id] = draft
        self.actualizados.append(event_id)
