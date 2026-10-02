from uuid import UUID

from app.application.repositories.kanban_repository import IKanbanColumnRepository
from app.domain.errors.kanban_errors import KanbanColumnNotFound


class DeleteKanbanColumnUseCase:
    def __init__(self, column_repo: IKanbanColumnRepository):
        self.column_repo = column_repo

    async def execute(self, column_id: UUID, user_id: UUID) -> None:
        column = await self.column_repo.get(column_id, user_id)
        if column is None:
            raise KanbanColumnNotFound(column_id)
        await self.column_repo.delete(column_id, user_id)