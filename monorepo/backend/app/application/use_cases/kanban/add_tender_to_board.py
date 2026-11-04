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
from app.domain.errors.kanban_errors import KanbanColumnNotFound, TenderAlreadyOnBoard


class AddTenderToBoardUseCase:
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
        column_id: UUID,
        position: int | None,
        tender_title: str | None = None,
    ) -> KanbanCard:
        column = await self.column_repo.get(column_id, supplier_id)
        if column is None:
            raise KanbanColumnNotFound(column_id)

        existing = await self.card_repo.get(supplier_id, tender_id)
        if existing is not None:
            raise TenderAlreadyOnBoard(supplier_id, tender_id)

        cards_in_column = [
            c
            for c in await self.card_repo.get_by_supplier_id(supplier_id)
            if c.column_id == column_id
        ]
        next_position = position if position is not None else len(cards_in_column)

        created = await self.card_repo.create(
            KanbanCard(
                supplier_id=supplier_id,
                user_id=user_id,
                tender_id=tender_id,
                column_id=column_id,
                position=next_position,
            )
        )

        if self.event_repo is not None:
            await RecordKanbanEventUseCase(self.event_repo).execute(
                supplier_id=supplier_id,
                user_id=user_id,
                event_type="card_added",
                entity_type="card",
                entity_id=created.id,
                tender_id=tender_id,
                tender_title=tender_title,
                details={"column_id": str(column_id), "column_name": column.name},
            )

        return created
