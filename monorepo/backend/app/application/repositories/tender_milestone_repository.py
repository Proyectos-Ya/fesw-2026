from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.tender_milestone import TenderMilestone


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
