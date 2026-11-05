from uuid import UUID

from app.application.repositories.kanban_event_repository import (
    IKanbanEventRepository,
)
from app.application.repositories.kanban_repository import IKanbanColumnRepository
from app.application.use_cases.kanban.record_kanban_event import (
    RecordKanbanEventUseCase,
)
from app.domain.errors.kanban_errors import KanbanColumnNotFound


class DeleteKanbanColumnUseCase:
    def __init__(
        self,
        column_repo: IKanbanColumnRepository,
        event_repo: IKanbanEventRepository | None = None,
    ):
        self.column_repo = column_repo
        self.event_repo = event_repo

    async def execute(
        self, column_id: UUID, supplier_id: UUID, user_id: UUID
    ) -> None:
        column = await self.column_repo.get(column_id, supplier_id)
        if column is None:
            raise KanbanColumnNotFound(column_id)
        await self.column_repo.delete(column_id, supplier_id)
        if self.event_repo is not None:
            await RecordKanbanEventUseCase(self.event_repo).execute(
                supplier_id=supplier_id,
                user_id=user_id,
                event_type="column_deleted",
                entity_type="column",
                entity_id=column_id,
                details={"name": column.name},
            )
