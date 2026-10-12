from uuid import UUID

from app.application.repositories.kanban_repository import IKanbanColumnRepository
from app.application.schemas.kanban_schema import KanbanColumnResponse
from app.domain.entities.kanban import DEFAULT_COLUMN_COLORS, DEFAULT_COLUMNS, KanbanColumn


class ListKanbanColumnsUseCase:
    def __init__(self, column_repo: IKanbanColumnRepository):
        self.column_repo = column_repo

    async def execute(self, user_id: UUID) -> list[KanbanColumnResponse]:
        columns = await self.column_repo.get_by_user_id(user_id)

        if not columns:
            columns = []
            for i, (name, color) in enumerate(zip(DEFAULT_COLUMNS, DEFAULT_COLUMN_COLORS)):
                col = await self.column_repo.create(
                    KanbanColumn(user_id=user_id, name=name, position=i, color=color)
                )
                columns.append(col)

        result = []
        for col in sorted(columns, key=lambda c: c.position):
            count = await self.column_repo.count_cards(col.id)
            result.append(
                KanbanColumnResponse(
                    id=col.id,
                    name=col.name,
                    position=col.position,
                    color=col.color,
                    card_count=count,
                    created_at=col.created_at,
                )
            )
        return result
