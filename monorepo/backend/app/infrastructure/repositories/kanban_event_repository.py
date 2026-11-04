"""Implementación SQL del repositorio de eventos del tablero kanban (HU-18)."""

from typing import cast
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.kanban_event_repository import (
    IKanbanEventRepository,
)
from app.domain.entities.kanban_event import (
    KanbanEntityType,
    KanbanEvent,
    KanbanEventType,
)
from app.infrastructure.repositories.kanban_event_model import KanbanEventModel


class KanbanEventRepository(IKanbanEventRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: KanbanEventModel) -> KanbanEvent:
        return KanbanEvent(
            id=model.id,
            supplier_id=model.supplier_id,
            user_id=model.user_id,
            event_type=cast(KanbanEventType, model.event_type),
            entity_type=cast(KanbanEntityType | None, model.entity_type),
            entity_id=model.entity_id,
            tender_id=model.tender_id,
            tender_title=model.tender_title,
            details=model.details or {},
            created_at=model.created_at,
        )

    async def save(self, event: KanbanEvent) -> KanbanEvent:
        model = KanbanEventModel(
            id=event.id,
            supplier_id=event.supplier_id,
            user_id=event.user_id,
            event_type=event.event_type,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            tender_id=event.tender_id,
            tender_title=event.tender_title,
            details=event.details,
            created_at=event.created_at,
        )
        self.session.add(model)
        await self.session.commit()
        return self._to_entity(model)

    async def list_by_supplier(
        self, supplier_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[KanbanEvent]:
        result = await self.session.exec(
            select(KanbanEventModel)
            .where(KanbanEventModel.supplier_id == supplier_id)
            .order_by(KanbanEventModel.created_at.desc())  # type: ignore[union-attr]
            .limit(limit)
            .offset(offset)
        )
        return [self._to_entity(m) for m in result.all()]
