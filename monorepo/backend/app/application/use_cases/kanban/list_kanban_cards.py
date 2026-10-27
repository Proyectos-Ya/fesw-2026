from uuid import UUID

from app.application.repositories.kanban_repository import IKanbanCardRepository
from app.domain.entities.kanban import KanbanCard


class ListKanbanCardsUseCase:
    def __init__(self, card_repo: IKanbanCardRepository):
        self.card_repo = card_repo

    async def execute(self, supplier_id: UUID) -> list[KanbanCard]:
        return await self.card_repo.get_by_supplier_id(supplier_id)
