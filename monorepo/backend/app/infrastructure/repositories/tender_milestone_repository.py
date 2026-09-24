from uuid import UUID

from sqlalchemy import delete
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.tender_milestone_repository import (
    ITenderMilestoneRepository,
)
from app.domain.entities.tender_milestone import (
    MilestoneKind,
    MilestoneSource,
    TenderMilestone,
)
from app.infrastructure.repositories.tender_milestone_model import TenderMilestoneModel


class TenderMilestoneRepository(ITenderMilestoneRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_entity(model: TenderMilestoneModel) -> TenderMilestone:
        return TenderMilestone(
            id=model.id,
            user_id=model.user_id,
            tender_id=model.tender_id,
            kind=MilestoneKind(model.kind),
            title=model.title,
            description=model.description,
            source=MilestoneSource(model.source),
            source_document_id=model.source_document_id,
            source_excerpt=model.source_excerpt,
            due_at=model.due_at,
            has_time=model.has_time,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_model(entity: TenderMilestone) -> TenderMilestoneModel:
        return TenderMilestoneModel(**entity.model_dump())

    async def list_for_tender(self, user_id: UUID, tender_id: UUID) -> list[TenderMilestone]:
        result = await self.session.exec(
            select(TenderMilestoneModel)
            .where(
                TenderMilestoneModel.user_id == user_id,
                TenderMilestoneModel.tender_id == tender_id,
            )
            .order_by(col(TenderMilestoneModel.due_at))
        )
        return [self._to_entity(m) for m in result.all()]

    async def list_by_ids(self, user_id: UUID, milestone_ids: list[UUID]) -> list[TenderMilestone]:
        if not milestone_ids:
            return []
        result = await self.session.exec(
            select(TenderMilestoneModel)
            .where(
                TenderMilestoneModel.user_id == user_id,
                col(TenderMilestoneModel.id).in_(milestone_ids),
            )
            .order_by(col(TenderMilestoneModel.due_at))
        )
        return [self._to_entity(m) for m in result.all()]

    async def save_many(self, milestones: list[TenderMilestone]) -> None:
        try:
            for milestone in milestones:
                await self.session.merge(self._to_model(milestone))
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    async def delete_many(self, user_id: UUID, milestone_ids: list[UUID]) -> None:
        if not milestone_ids:
            return
        await self.session.exec(
            delete(TenderMilestoneModel).where(
                col(TenderMilestoneModel.user_id) == user_id,
                col(TenderMilestoneModel.id).in_(milestone_ids),
            )
        )
        await self.session.commit()
