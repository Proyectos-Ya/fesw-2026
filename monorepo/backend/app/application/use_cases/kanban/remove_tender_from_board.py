from uuid import UUID

from app.application.repositories.kanban_repository import IKanbanCardRepository
from app.domain.errors.kanban_errors import KanbanCardNotFound


class RemoveTenderFromBoardUseCase:
    def __init__(self, card_repo: IKanbanCardRepository):
        self.card_repo = card_repo

    async def execute(self, user_id: UUID, tender_id: UUID) -> None:
        card = await self.card_repo.get(user_id, tender_id)
        if card is None:
            raise KanbanCardNotFound(user_id, tender_id)
        await self.card_repo.delete(user_id, tender_id)
