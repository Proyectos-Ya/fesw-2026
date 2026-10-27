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


class ReorderKanbanColumnsUseCase:
    """Reordena las columnas Kanban del workspace en bloque.

    La lista `column_ids` debe contener exactamente **todas** las columnas del
    workspace, sin duplicados; cada id se asigna a `position = índice en la lista`.
    """

    def __init__(
        self,
        column_repo: IKanbanColumnRepository,
        event_repo: IKanbanEventRepository | None = None,
    ):
        self.column_repo = column_repo
        self.event_repo = event_repo

    async def execute(
        self, supplier_id: UUID, user_id: UUID, column_ids: list[UUID]
    ) -> list[KanbanColumn]:
        if len(column_ids) != len(set(column_ids)):
            raise ValueError("La lista de columnas contiene ids duplicados.")

        existing = await self.column_repo.get_by_supplier_id(supplier_id)
        existing_ids = {c.id for c in existing}

        for col_id in column_ids:
            if col_id not in existing_ids:
                raise KanbanColumnNotFound(col_id)

        if len(column_ids) != len(existing_ids):
            raise ValueError(
                "La lista de columnas está incompleta: debe incluir todas las "
                "columnas del workspace."
            )

        reordered = await self.column_repo.reorder(
            supplier_id=supplier_id, ordered_ids=column_ids
        )

        if self.event_repo is not None:
            await RecordKanbanEventUseCase(self.event_repo).execute(
                supplier_id=supplier_id,
                user_id=user_id,
                event_type="column_reordered",
                entity_type="column",
                details={"ordered_ids": [str(cid) for cid in column_ids]},
            )

        return reordered
