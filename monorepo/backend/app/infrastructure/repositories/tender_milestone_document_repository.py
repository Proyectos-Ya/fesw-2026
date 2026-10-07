from datetime import datetime
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.milestone_document_repository import (
    IMilestoneDocumentRepository,
)
from app.infrastructure.repositories.tender_milestone_document_model import (
    TenderMilestoneDocumentModel,
)


class TenderMilestoneDocumentRepository(IMilestoneDocumentRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_processed(self, user_id: UUID, tender_id: UUID) -> set[UUID]:
        resultado = await self.session.exec(
            select(TenderMilestoneDocumentModel.document_id).where(
                TenderMilestoneDocumentModel.user_id == user_id,
                TenderMilestoneDocumentModel.tender_id == tender_id,
            )
        )
        return set(resultado.all())

    async def mark_processed(
        self,
        user_id: UUID,
        tender_id: UUID,
        document_id: UUID,
        milestones_found: int,
        now: datetime,
    ) -> None:
        # `merge` actualiza si ya existía: marcar dos veces no falla.
        await self.session.merge(
            TenderMilestoneDocumentModel(
                document_id=document_id,
                user_id=user_id,
                tender_id=tender_id,
                extracted_at=now,
                milestones_found=milestones_found,
            )
        )
        await self.session.commit()
