from uuid import UUID

from app.application.repositories.kanban_repository import IKanbanColumnRepository
from app.domain.entities.kanban import DEFAULT_COLUMN_COLORS, KanbanColumn


class CreateKanbanColumnUseCase:
    def __init__(self, column_repo: IKanbanColumnRepository):
        self.column_repo = column_repo

    async def execute(
        self, user_id: UUID, name: str, position: int | None, color: str | None = None
    ) -> KanbanColumn:
        columns = await self.column_repo.get_by_user_id(user_id)
        next_position = position if position is not None else len(columns)
        assigned_color = color or DEFAULT_COLUMN_COLORS[next_position % len(DEFAULT_COLUMN_COLORS)]
        return await self.column_repo.create(
            KanbanColumn(user_id=user_id, name=name, position=next_position, color=assigned_color)
        )
