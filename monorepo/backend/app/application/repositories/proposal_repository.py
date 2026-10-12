from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.proposal import ProposalDraft


class IProposalDraftRepository(ABC):
    """Borradores de postulación: a lo sumo uno por empresa y licitación."""

    @abstractmethod
    async def get(self, supplier_id: UUID, tender_id: UUID) -> ProposalDraft | None: ...

    @abstractmethod
    async def save(self, draft: ProposalDraft) -> ProposalDraft:
        """Crea o actualiza el borrador (por su id) y confirma.

        Un segundo borrador para la misma empresa y licitación viola la
        restricción única: quien crea uno debe haber buscado antes con `get`.
        """
