from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.entities.kanban import KanbanCard, KanbanColumn


class IKanbanColumnRepository(ABC):
    """Repositorio de columnas del tablero kanban.

    HU-18: el scoping es por workspace (`supplier_id`); `user_id` queda solo
    como autoría dentro de la entidad.
    """

    @abstractmethod
    async def get_by_supplier_id(self, supplier_id: UUID) -> list[KanbanColumn]:
        pass

    @abstractmethod
    async def get(self, column_id: UUID, supplier_id: UUID) -> KanbanColumn | None:
        pass

    @abstractmethod
    async def update(self, column: KanbanColumn) -> KanbanColumn:
        pass

    @abstractmethod
    async def create(self, column: KanbanColumn) -> KanbanColumn:
        pass

    @abstractmethod
    async def delete(self, column_id: UUID, supplier_id: UUID) -> bool:
        pass

    @abstractmethod
    async def count_cards(self, column_id: UUID) -> int:
        pass

    @abstractmethod
    async def reorder(
        self, supplier_id: UUID, ordered_ids: list[UUID]
    ) -> list[KanbanColumn]:
        """Reordena las columnas del workspace según el orden dado.

        Asigna `position = índice en ordered_ids` a cada columna, en una sola
        operación transaccional. Devuelve las columnas del workspace con las
        nuevas posiciones aplicadas.
        """
        pass


class IKanbanCardRepository(ABC):
    """Repositorio de tarjetas del tablero kanban (workspace-scoped, HU-18)."""

    @abstractmethod
    async def get_by_supplier_id(self, supplier_id: UUID) -> list[KanbanCard]:
        """Tarjetas activas (no archivadas) del workspace."""
        pass

    @abstractmethod
    async def get(self, supplier_id: UUID, tender_id: UUID) -> KanbanCard | None:
        """Tarjeta activa (no archivada) por par workspace/licitación."""
        pass

    @abstractmethod
    async def get_by_id(self, card_id: UUID, supplier_id: UUID) -> KanbanCard | None:
        """Tarjeta por ID, archivada o no. Necesario para archivar/restaurar."""
        pass

    @abstractmethod
    async def create(self, card: KanbanCard) -> KanbanCard:
        pass

    @abstractmethod
    async def update(self, card: KanbanCard) -> KanbanCard:
        pass

    @abstractmethod
    async def delete(self, supplier_id: UUID, tender_id: UUID) -> bool:
        pass

    @abstractmethod
    async def list_archived(self, supplier_id: UUID) -> list[KanbanCard]:
        """Historial del workspace, orden descendente por `archived_at`."""
        pass

    @abstractmethod
    async def list_archived_with_context(
        self, supplier_id: UUID
    ) -> list[tuple[KanbanCard, str, str, str]]:
        """Historial enriquecido para el panel: cada fila incluye
        `(card, column_name, tender_code, tender_name)`.

        Hace la unión en SQL para evitar N+1 al pintar el panel.
        Orden descendente por `archived_at`.
        """
        pass

    @abstractmethod
    async def list_candidates_for_auto_archive(
        self, cutoff: datetime
    ) -> list[KanbanCard]:
        """Tarjetas activas con `board_entered_at` menor que `cutoff`.

        El scheduler usa esto para marcar como `auto_3m`. Devolver entidades
        (no modelos) mantiene la dependencia unidireccional hacia dominio.
        """
        pass
