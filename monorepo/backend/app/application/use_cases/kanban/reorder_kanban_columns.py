from uuid import UUID

from app.application.repositories.kanban_repository import IKanbanColumnRepository
from app.domain.entities.kanban import KanbanColumn
from app.domain.errors.kanban_errors import KanbanColumnNotFound


class ReorderKanbanColumnsUseCase:
    """Reordena las columnas Kanban de un usuario en bloque.

    La lista `column_ids` debe contener exactamente **todas** las columnas del
    usuario, sin duplicados; cada id se asigna a `position = índice en la lista`.
    """

    def __init__(self, column_repo: IKanbanColumnRepository):
        self.column_repo = column_repo

    async def execute(
        self, user_id: UUID, column_ids: list[UUID]
    ) -> list[KanbanColumn]:
        if len(column_ids) != len(set(column_ids)):
            raise ValueError("La lista de columnas contiene ids duplicados.")

        existing = await self.column_repo.get_by_user_id(user_id)
        existing_ids = {c.id for c in existing}

        for col_id in column_ids:
            if col_id not in existing_ids:
                raise KanbanColumnNotFound(col_id)

        if len(column_ids) != len(existing_ids):
            raise ValueError(
                "La lista de columnas está incompleta: debe incluir todas las "
                "columnas del usuario."
            )

        return await self.column_repo.reorder(user_id=user_id, ordered_ids=column_ids)
