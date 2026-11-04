from uuid import UUID

from app.application.repositories.kanban_event_repository import (
    IKanbanEventRepository,
)
from app.application.repositories.kanban_repository import IKanbanColumnRepository
from app.application.use_cases.kanban.record_kanban_event import (
    RecordKanbanEventUseCase,
)
from app.domain.entities.kanban import KanbanColumn
from app.domain.errors.kanban_errors import KanbanColumnNotFound


class UpdateKanbanColumnUseCase:
    def __init__(
        self,
        column_repo: IKanbanColumnRepository,
        event_repo: IKanbanEventRepository | None = None,
    ):
        self.column_repo = column_repo
        self.event_repo = event_repo

    async def execute(
        self,
        column_id: UUID,
        supplier_id: UUID,
        user_id: UUID,
        name: str | None,
        position: int | None,
        color: str | None = None,
    ) -> KanbanColumn:
        column = await self.column_repo.get(column_id, supplier_id)
        if column is None:
            raise KanbanColumnNotFound(column_id)

        old_name = column.name
        old_color = column.color
        old_position = column.position

        if name is not None:
            column.name = name
        if position is not None:
            column.position = position
        if color is not None:
            column.color = color

        updated = await self.column_repo.update(column)

        if self.event_repo is not None:
            recorder = RecordKanbanEventUseCase(self.event_repo)
            if name is not None and name != old_name:
                await recorder.execute(
                    supplier_id=supplier_id,
                    user_id=user_id,
                    event_type="column_renamed",
                    entity_type="column",
                    entity_id=updated.id,
                    details={"old_name": old_name, "new_name": name},
                )
            if color is not None and color != old_color:
                await recorder.execute(
                    supplier_id=supplier_id,
                    user_id=user_id,
                    event_type="column_recolored",
                    entity_type="column",
                    entity_id=updated.id,
                    details={"old_color": old_color, "new_color": color},
                )
            if position is not None and position != old_position:
                await recorder.execute(
                    supplier_id=supplier_id,
                    user_id=user_id,
                    event_type="column_reordered",
                    entity_type="column",
                    entity_id=updated.id,
                    details={"old_position": old_position, "new_position": position},
                )

        return updated
