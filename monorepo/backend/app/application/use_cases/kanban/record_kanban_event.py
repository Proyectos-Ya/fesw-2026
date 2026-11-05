"""Caso de uso: registrar un evento en el historial del tablero (HU-18).

Se invoca sincrónicamente desde cada caso de uso de mutación kanban dentro
del mismo commit de transacción: si falla el evento, falla la operación.

El `tender_title` se desnormaliza al momento de grabar (lo recibe quien
dispara el evento, no se re-busca acá) para no acoplar este use case con
el repo de tenders ni introducir una query extra.
"""

from typing import Any
from uuid import UUID

from app.application.repositories.kanban_event_repository import (
    IKanbanEventRepository,
)
from app.domain.entities.kanban_event import (
    KanbanEntityType,
    KanbanEvent,
    KanbanEventType,
)


class RecordKanbanEventUseCase:
    def __init__(self, event_repo: IKanbanEventRepository):
        self.event_repo = event_repo

    async def execute(
        self,
        *,
        supplier_id: UUID,
        user_id: UUID,
        event_type: KanbanEventType,
        entity_type: KanbanEntityType | None = None,
        entity_id: UUID | None = None,
        tender_id: UUID | None = None,
        tender_title: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> KanbanEvent:
        event = KanbanEvent(
            supplier_id=supplier_id,
            user_id=user_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            tender_id=tender_id,
            tender_title=tender_title,
            details=details or {},
        )
        return await self.event_repo.save(event)
