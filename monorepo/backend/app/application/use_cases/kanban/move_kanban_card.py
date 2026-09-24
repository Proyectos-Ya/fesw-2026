from uuid import UUID

from app.application.repositories.kanban_repository import (
    IKanbanCardRepository,
    IKanbanColumnRepository,
)
from app.domain.entities.kanban import KanbanCard
from app.domain.errors.kanban_errors import KanbanCardNotFound, KanbanColumnNotFound
from app.shared.datetime_utils import utc_now_naive


class MoveKanbanCardUseCase:
    def __init__(
        self,
        card_repo: IKanbanCardRepository,
        column_repo: IKanbanColumnRepository,
    ):
        self.card_repo = card_repo
        self.column_repo = column_repo

    async def execute(
        self,
        user_id: UUID,
        tender_id: UUID,
        column_id: UUID | None,
        position: int | None,
    ) -> KanbanCard:
        card = await self.card_repo.get(user_id, tender_id)
        if card is None:
            raise KanbanCardNotFound(user_id, tender_id)

        if column_id is not None:
            column = await self.column_repo.get(column_id, user_id)
            if column is None:
                raise KanbanColumnNotFound(column_id)
            card.column_id = column_id

        if position is not None:
            card.position = position

        card.updated_at = utc_now_naive()
        return await self.card_repo.update(card)
