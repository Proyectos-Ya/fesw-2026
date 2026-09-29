from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.entities.tender_milestone import MilestoneSource, TenderMilestone


class ITenderMilestoneRepository(ABC):
    @abstractmethod
    async def list_for_tender(self, user_id: UUID, tender_id: UUID) -> list[TenderMilestone]:
        """Hitos del usuario para la licitación, del más próximo al más lejano."""

    @abstractmethod
    async def list_by_ids(self, user_id: UUID, milestone_ids: list[UUID]) -> list[TenderMilestone]:
        """Solo devuelve los que pertenecen al usuario."""

    @abstractmethod
    async def save_many(self, milestones: list[TenderMilestone]) -> None:
        """Inserta o actualiza por id."""

    @abstractmethod
    async def delete_many(self, user_id: UUID, milestone_ids: list[UUID]) -> None: ...

    @abstractmethod
    async def list_pending_reminders(self, now: datetime) -> list[TenderMilestone]:
        """De todos los usuarios: hitos a los que toca recordar ahora."""

    @abstractmethod
    async def set_reminder(
        self, user_id: UUID, milestone_id: UUID, days_before: int | None
    ) -> TenderMilestone | None:
        """Activa o apaga el recordatorio. None si el hito no es del usuario."""

    @abstractmethod
    async def list_by_tender_and_source(
        self, tender_id: UUID, source: MilestoneSource
    ) -> list[TenderMilestone]:
        """De todos los usuarios: lo usa el refresco de fechas oficiales."""
