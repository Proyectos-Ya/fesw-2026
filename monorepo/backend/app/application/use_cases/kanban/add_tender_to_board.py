from uuid import UUID

from app.application.repositories.kanban_repository import (
    IKanbanCardRepository,
    IKanbanColumnRepository,
)
from app.domain.entities.kanban import KanbanCard
from app.domain.errors.kanban_errors import KanbanColumnNotFound, TenderAlreadyOnBoard


class AddTenderToBoardUseCase:
    def __init__(
        self,
        card_repo: IKanbanCardRepository,
        column_repo: IKanbanColumnRepository,
    ):
        self.card_repo = card_repo
        self.column_repo = column_repo

    async def execute(
        self, user_id: UUID, tender_id: UUID, column_id: UUID, position: int | None
    ) -> KanbanCard:
        column = await self.column_repo.get(column_id, user_id)
        if column is None:
            raise KanbanColumnNotFound(column_id)

        existing = await self.card_repo.get(user_id, tender_id)
        if existing is not None:
            raise TenderAlreadyOnBoard(user_id, tender_id)

        cards_in_column = [
            c for c in await self.card_repo.get_by_user_id(user_id)
            if c.column_id == column_id
        ]
        next_position = position if position is not None else len(cards_in_column)

        return await self.card_repo.create(
            KanbanCard(
                user_id=user_id,
                tender_id=tender_id,
                column_id=column_id,
                position=next_position,
            )
        )
