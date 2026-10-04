from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.entities.tender_share_link import TenderShareLink


class ITenderShareLinkRepository(ABC):
    @abstractmethod
    async def save(self, link: TenderShareLink) -> TenderShareLink:
        """Crea el enlace o actualiza el existente con el mismo id."""

    @abstractmethod
    async def get(self, link_id: UUID) -> TenderShareLink | None: ...

    @abstractmethod
    async def get_by_token_hash(self, token_hash: str) -> TenderShareLink | None: ...

    @abstractmethod
    async def list_active(
        self, tender_id: UUID, supplier_id: UUID, now: datetime
    ) -> list[TenderShareLink]:
        """Los enlaces vigentes de una licitación y empresa, del más nuevo al más viejo."""
