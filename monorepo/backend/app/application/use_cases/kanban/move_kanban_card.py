from uuid import UUID

from app.application.repositories.kanban_event_repository import (
    IKanbanEventRepository,
)
from app.application.repositories.kanban_repository import (
    IKanbanCardRepository,
    IKanbanColumnRepository,
)
from app.application.use_cases.kanban.record_kanban_event import (
    RecordKanbanEventUseCase,
)
from app.domain.entities.kanban import KanbanCard
from app.domain.errors.kanban_errors import KanbanCardNotFound, KanbanColumnNotFound
from app.shared.datetime_utils import utc_now_naive


class MoveKanbanCardUseCase:
    def __init__(
        self,
        card_repo: IKanbanCardRepository,
        column_repo: IKanbanColumnRepository,
        event_repo: IKanbanEventRepository | None = None,
    ):
        self.card_repo = card_repo
        self.column_repo = column_repo
        self.event_repo = event_repo

    async def execute(
        self,
        supplier_id: UUID,
        user_id: UUID,
        tender_id: UUID,
        column_id: UUID | None,
        position: int | None,
        tender_title: str | None = None,
    ) -> KanbanCard:
        card = await self.card_repo.get(supplier_id, tender_id)
        if card is None:
            raise KanbanCardNotFound(supplier_id, tender_id)

        old_column_id = card.column_id
        old_column = await self.column_repo.get(old_column_id, supplier_id)
        new_column = old_column

        if column_id is not None and column_id != old_column_id:
            new_column = await self.column_repo.get(column_id, supplier_id)
            if new_column is None:
                raise KanbanColumnNotFound(column_id)
            card.column_id = column_id

        if position is not None:
            card.position = position

        card.updated_at = utc_now_naive()
        updated = await self.card_repo.update(card)

        if self.event_repo is not None and new_column is not None and old_column is not None:
            await RecordKanbanEventUseCase(self.event_repo).execute(
                supplier_id=supplier_id,
                user_id=user_id,
                event_type="card_moved",
                entity_type="card",
                entity_id=updated.id,
                tender_id=tender_id,
                tender_title=tender_title,
                details={
                    "from_column_id": str(old_column_id),
                    "from_column": old_column.name,
                    "to_column_id": str(updated.column_id),
                    "to_column": new_column.name,
                },
            )

        return updated
