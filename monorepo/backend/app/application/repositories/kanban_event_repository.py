"""Interfaz del repositorio de eventos del tablero kanban (HU-18).

Los eventos se escriben sincrónicamente dentro del mismo caso de uso que
dispara la mutación (misma transacción). La lectura paginada alimenta el
panel de historial del workspace.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.kanban_event import KanbanEvent


class IKanbanEventRepository(ABC):
    @abstractmethod
    async def save(self, event: KanbanEvent) -> KanbanEvent:
        """Agrega el evento. La tabla es append-only."""
        pass

    @abstractmethod
    async def list_by_supplier(
        self, supplier_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[KanbanEvent]:
        """Eventos del workspace en orden `created_at` descendente."""
        pass
