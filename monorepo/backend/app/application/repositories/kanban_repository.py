from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.kanban import KanbanCard, KanbanColumn

class IKanbanColumnRepository(ABC):

    @abstractmethod
    async def get_by_user_id(self, user_id:UUID) -> list[KanbanColumn]:
        pass


    @abstractmethod
    async def get(self, column_id:UUID, user_id:UUID) -> KanbanColumn | None:
        pass

    @abstractmethod
    async def update(self, column: KanbanColumn) -> KanbanColumn:
        pass

    @abstractmethod
    async def create(self, column: KanbanColumn) -> KanbanColumn:
        pass

    @abstractmethod
    async def delete(self, column_id: UUID, user_id: UUID) -> bool:
        pass

    @abstractmethod
    async def count_cards(self, column_id: UUID) -> int:
        pass


class IKanbanCardRepository(ABC):
    @abstractmethod
    async def get_by_user_id(self, user_id: UUID) -> list[KanbanCard]:
        pass

    @abstractmethod
    async def get(self, user_id: UUID, tender_id: UUID) -> KanbanCard | None:
        pass

    @abstractmethod
    async def create(self, card: KanbanCard) -> KanbanCard:
        pass

    @abstractmethod
    async def update(self, card: KanbanCard) -> KanbanCard:
        pass

    @abstractmethod
    async def delete(self, user_id: UUID, tender_id: UUID) -> bool:
        pass

