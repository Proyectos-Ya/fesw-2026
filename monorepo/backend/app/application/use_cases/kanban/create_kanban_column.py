from uuid import UUID

from app.application.repositories.kanban_event_repository import (
    IKanbanEventRepository,
)
from app.application.repositories.kanban_repository import IKanbanColumnRepository
from app.application.use_cases.kanban.record_kanban_event import (
    RecordKanbanEventUseCase,
)
from app.domain.entities.kanban import DEFAULT_COLUMN_COLORS, KanbanColumn


class CreateKanbanColumnUseCase:
    def __init__(
        self,
        column_repo: IKanbanColumnRepository,
        event_repo: IKanbanEventRepository | None = None,
    ):
        self.column_repo = column_repo
        self.event_repo = event_repo

    async def execute(
        self,
        supplier_id: UUID,
        user_id: UUID,
        name: str,
        position: int | None,
        color: str | None = None,
    ) -> KanbanColumn:
        columns = await self.column_repo.get_by_supplier_id(supplier_id)
        next_position = position if position is not None else len(columns)
        assigned_color = color or DEFAULT_COLUMN_COLORS[
            next_position % len(DEFAULT_COLUMN_COLORS)
        ]
        created = await self.column_repo.create(
            KanbanColumn(
                supplier_id=supplier_id,
                user_id=user_id,
                name=name,
                position=next_position,
                color=assigned_color,
            )
        )
        if self.event_repo is not None:
            await RecordKanbanEventUseCase(self.event_repo).execute(
                supplier_id=supplier_id,
                user_id=user_id,
                event_type="column_created",
                entity_type="column",
                entity_id=created.id,
                details={"name": name, "position": next_position},
            )
        return created
