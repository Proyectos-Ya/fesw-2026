"""Caso de uso: listar el historial del tablero del workspace (HU-18)."""

from uuid import UUID

from app.application.repositories.kanban_event_repository import (
    IKanbanEventRepository,
)
from app.domain.entities.kanban_event import KanbanEvent


class ListKanbanEventsUseCase:
    def __init__(self, event_repo: IKanbanEventRepository):
        self.event_repo = event_repo

    async def execute(
        self, supplier_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[KanbanEvent]:
        return await self.event_repo.list_by_supplier(
            supplier_id=supplier_id, limit=limit, offset=offset
        )
