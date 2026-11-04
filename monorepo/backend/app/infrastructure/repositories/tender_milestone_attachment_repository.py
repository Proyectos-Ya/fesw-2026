from datetime import datetime
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.milestone_attachment_repository import (
    IMilestoneAttachmentRepository,
)
from app.infrastructure.repositories.tender_milestone_attachment_model import (
    TenderMilestoneAttachmentModel,
)


class TenderMilestoneAttachmentRepository(IMilestoneAttachmentRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_processed(self, user_id: UUID, tender_id: UUID) -> set[UUID]:
        resultado = await self.session.exec(
            select(TenderMilestoneAttachmentModel.attachment_file_id).where(
                TenderMilestoneAttachmentModel.user_id == user_id,
                TenderMilestoneAttachmentModel.tender_id == tender_id,
            )
        )
        return set(resultado.all())

    async def mark_processed(
        self,
        user_id: UUID,
        tender_id: UUID,
        attachment_file_id: UUID,
        milestones_found: int,
        now: datetime,
    ) -> None:
        # `merge` actualiza si ya existía: marcar dos veces no falla.
        await self.session.merge(
            TenderMilestoneAttachmentModel(
                user_id=user_id,
                attachment_file_id=attachment_file_id,
                tender_id=tender_id,
                extracted_at=now,
                milestones_found=milestones_found,
            )
        )
        await self.session.commit()
