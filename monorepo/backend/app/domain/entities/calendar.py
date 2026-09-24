from datetime import timedelta
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel

from app.domain.entities.tender_milestone import TenderMilestone
from app.domain.errors.calendar_errors import MilestoneTimeRequired
from app.shared.datetime_utils import UtcDateTime

_DURACION_EVENTO = timedelta(hours=1)
_RECORDATORIOS_MINUTOS = (24 * 60, 60)


class CalendarProvider(StrEnum):
    GOOGLE = "google"


class CalendarEventDraft(BaseModel):
    """Evento listo para enviar a un calendario externo."""

    milestone_id: UUID
    title: str
    description: str
    start: UtcDateTime
    end: UtcDateTime
    reminders_minutes: tuple[int, ...]

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
        )
