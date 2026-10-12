from datetime import datetime
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.tender_share_link_repository import (
    ITenderShareLinkRepository,
)
from app.domain.entities.tender_share_link import TenderShareLink
from app.infrastructure.repositories.tender_share_link_model import (
    TenderShareLinkModel,
)


class TenderShareLinkRepository(ITenderShareLinkRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_entity(model: TenderShareLinkModel) -> TenderShareLink:
        return TenderShareLink(
            id=model.id,
            token_hash=model.token_hash,
            tender_id=model.tender_id,
            supplier_id=model.supplier_id,
            created_by=model.created_by,
            created_at=model.created_at,
            expires_at=model.expires_at,
            revoked_at=model.revoked_at,
        )

    async def save(self, link: TenderShareLink) -> TenderShareLink:
        try:
            await self.session.merge(TenderShareLinkModel(**link.model_dump()))
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return link

    async def get(self, link_id: UUID) -> TenderShareLink | None:
        model = await self.session.get(TenderShareLinkModel, link_id)
        return self._to_entity(model) if model is not None else None

    async def get_by_token_hash(self, token_hash: str) -> TenderShareLink | None:
        result = await self.session.exec(
            select(TenderShareLinkModel).where(
                TenderShareLinkModel.token_hash == token_hash
            )
        )
        model = result.first()
        return self._to_entity(model) if model is not None else None

    async def list_active(
        self, tender_id: UUID, supplier_id: UUID, now: datetime
    ) -> list[TenderShareLink]:
        result = await self.session.exec(
            select(TenderShareLinkModel)
            .where(
                TenderShareLinkModel.tender_id == tender_id,
                TenderShareLinkModel.supplier_id == supplier_id,
                col(TenderShareLinkModel.revoked_at).is_(None),
                col(TenderShareLinkModel.expires_at) > now,
            )
            .order_by(col(TenderShareLinkModel.created_at).desc())
        )
        return [self._to_entity(m) for m in result.all()]
