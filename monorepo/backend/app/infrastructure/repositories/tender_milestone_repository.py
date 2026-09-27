from datetime import datetime
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
from app.shared.datetime_utils import utc_now_naive


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
            reminder_days_before=model.reminder_days_before,
            reminder_sent_at=model.reminder_sent_at,
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

    async def list_pending_reminders(self, now: datetime) -> list[TenderMilestone]:
        """Hitos con recordatorio activo cuya ventana de aviso ya empezó.

        El filtro fino (la ventana depende de `reminder_days_before` de cada
        fila) lo hace el dominio; acá solo se acota con el índice para no traer
        la tabla entera.
        """
        result = await self.session.exec(
            select(TenderMilestoneModel).where(
                col(TenderMilestoneModel.reminder_days_before).is_not(None),
                col(TenderMilestoneModel.reminder_sent_at).is_(None),
                col(TenderMilestoneModel.due_at) > now,
            )
        )
        hitos = [self._to_entity(m) for m in result.all()]
        return [h for h in hitos if h.recordatorio_pendiente(now)]

    async def set_reminder(
        self, user_id: UUID, milestone_id: UUID, days_before: int | None
    ) -> TenderMilestone | None:
        """Activa o apaga el recordatorio. Devuelve None si el hito no es del usuario."""
        result = await self.session.exec(
            select(TenderMilestoneModel).where(
                TenderMilestoneModel.id == milestone_id,
                TenderMilestoneModel.user_id == user_id,
            )
        )
        model = result.first()
        if model is None:
            return None
        model.reminder_days_before = days_before
        # Cambiar la anticipación reabre la posibilidad de avisar.
        model.reminder_sent_at = None
        model.updated_at = utc_now_naive()
        guardado = self._to_entity(model)
        self.session.add(model)
        await self.session.commit()
        return guardado

    async def list_by_tender_and_source(
        self, tender_id: UUID, source: MilestoneSource
    ) -> list[TenderMilestone]:
        result = await self.session.exec(
            select(TenderMilestoneModel).where(
                TenderMilestoneModel.tender_id == tender_id,
                TenderMilestoneModel.source == source.value,
            )
        )
        return [self._to_entity(m) for m in result.all()]

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
