from uuid import UUID

from app.application.repositories.kanban_repository import IKanbanColumnRepository
from app.domain.entities.kanban import KanbanColumn
from app.domain.errors.kanban_errors import KanbanColumnNotFound


class UpdateKanbanColumnUseCase:
    def __init__(self, column_repo: IKanbanColumnRepository):
        self.column_repo = column_repo

    async def execute(
        self, column_id: UUID, user_id: UUID, name: str | None, position: int | None
    ) -> KanbanColumn:
        column = await self.column_repo.get(column_id, user_id)
        if column is None:
            raise KanbanColumnNotFound(column_id)

        if name is not None:
            column.name = name
        if position is not None:
            column.position = position

        return await self.column_repo.update(column)