"""Dobles en memoria para los enlaces compartidos (HdU 19)."""

from datetime import datetime
from uuid import UUID

from app.application.repositories.tender_share_link_repository import (
    ITenderShareLinkRepository,
)
from app.domain.entities.tender_share_link import ShareLinkStatus, TenderShareLink


class InMemoryTenderShareLinkRepository(ITenderShareLinkRepository):
    def __init__(self) -> None:
        self.links: dict[UUID, TenderShareLink] = {}

    async def save(self, link: TenderShareLink) -> TenderShareLink:
        self.links[link.id] = link
        return link

    async def get(self, link_id: UUID) -> TenderShareLink | None:
        return self.links.get(link_id)

    async def get_by_token_hash(self, token_hash: str) -> TenderShareLink | None:
        return next(
            (enlace for enlace in self.links.values() if enlace.token_hash == token_hash),
            None,
        )

    async def list_active(
        self, tender_id: UUID, supplier_id: UUID, now: datetime
    ) -> list[TenderShareLink]:
        vigentes = [
            enlace
            for enlace in self.links.values()
            if enlace.tender_id == tender_id
            and enlace.supplier_id == supplier_id
            and enlace.estado(now) is ShareLinkStatus.ACTIVO
        ]
        return sorted(vigentes, key=lambda enlace: enlace.created_at, reverse=True)
