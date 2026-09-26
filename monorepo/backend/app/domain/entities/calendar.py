from datetime import datetime, time, timedelta
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, SecretStr

from app.domain.entities.tender_milestone import TenderMilestone
from app.domain.errors.calendar_errors import MilestoneTimeRequired
from app.shared.datetime_utils import UtcDateTime, utc_now_naive

_DURACION_EVENTO = timedelta(hours=1)
_RECORDATORIOS_MINUTOS = (24 * 60, 60)
_MARGEN_REFRESCO = timedelta(minutes=1)


class CalendarProvider(StrEnum):
    GOOGLE = "google"


class CalendarConnectionStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class CalendarConnection(BaseModel):
    """Cuenta de calendario externa autorizada por un usuario.

    Los tokens van como `SecretStr` para que no se filtren en logs ni respuestas;
    el cifrado en reposo lo aplica el repositorio.
    """

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    provider: CalendarProvider
    access_token: SecretStr
    refresh_token: SecretStr
    expires_at: UtcDateTime
    account_email: str | None = None
    status: CalendarConnectionStatus = CalendarConnectionStatus.ACTIVE
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)
    updated_at: UtcDateTime = Field(default_factory=utc_now_naive)

    def needs_refresh(self, now: datetime) -> bool:
        return self.expires_at - _MARGEN_REFRESCO <= now


class CalendarOAuthState(BaseModel):
    """Autorización en curso: liga el `state` de OAuth a la sincronización pedida."""

    state_hash: str
    user_id: UUID
    provider: CalendarProvider
    tender_id: UUID
    milestone_ids: list[UUID]
    default_time: time | None = None
    expires_at: UtcDateTime
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)

    def is_valid_for(self, user_id: UUID, now: datetime) -> bool:
        return self.user_id == user_id and now < self.expires_at


class CalendarEventLink(BaseModel):
    """Evento externo creado para un hito, para actualizarlo en vez de duplicarlo."""

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    milestone_id: UUID
    provider: CalendarProvider
    external_event_id: str
    synced_due_at: UtcDateTime
    last_synced_at: UtcDateTime = Field(default_factory=utc_now_naive)


class CalendarEventDraft(BaseModel):
    """Evento listo para enviar a un calendario externo."""

    milestone_id: UUID
    title: str
    description: str
    start: UtcDateTime
    end: UtcDateTime
    reminders_minutes: tuple[int, ...]
    return_url: str

    @classmethod
    def from_milestone(
        cls, milestone: TenderMilestone, *, tender_title: str, return_url: str
    ) -> "CalendarEventDraft":
        if not milestone.has_time:
            raise MilestoneTimeRequired([milestone.id])
        enlace = f"Ver la licitación en ProyectosYA: {return_url}"
        description = f"{milestone.description}\n\n{enlace}" if milestone.description else enlace
        return cls(
            milestone_id=milestone.id,
            title=f"{milestone.title} — {tender_title}",
            description=description,
            start=milestone.due_at,
            end=milestone.due_at + _DURACION_EVENTO,
            reminders_minutes=_RECORDATORIOS_MINUTOS,
            return_url=return_url,
        )
