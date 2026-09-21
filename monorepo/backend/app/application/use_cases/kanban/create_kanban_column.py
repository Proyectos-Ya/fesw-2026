from uuid import UUID

from app.application.repositories.kanban_repository import IKanbanColumnRepository
from app.domain.entities.kanban import KanbanColumn

class CreateKanbanColumnUseCase:
    def __init__(self, column_repo: IKanbanColumnRepository):
        self.column_repo = column_repo

    async def execute(self, user_id: UUID, name: str, position: int | None) -> KanbanColumn:
        columns = await self.column_repo.get_by_user_id(user_id)
        next_position = position if position is not None else len(columns)
        return await self.column_repo.create(
            KanbanColumn(user_id=user_id, name=name, position=next_position)
        )