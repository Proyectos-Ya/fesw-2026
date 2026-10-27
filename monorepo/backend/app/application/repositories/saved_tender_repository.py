from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.saved_tender import SavedTender


class ISavedTenderRepository(ABC):
    """Persistencia de las licitaciones guardadas del workspace (HU-18).

    Scoping por `supplier_id`: todos los miembros del workspace comparten la
    misma lista. `user_id` queda como auditoría dentro de `SavedTender` (quién
    la guardó primero), no como criterio de filtrado.
    """

    @abstractmethod
    async def get_by_supplier_id(self, supplier_id: UUID) -> list[SavedTender]:
        """Todas las licitaciones guardadas del workspace."""
        pass

    @abstractmethod
    async def get(self, supplier_id: UUID, tender_id: UUID) -> SavedTender | None:
        """Marca sobre una licitación del workspace, si existe."""
        pass

    @abstractmethod
    async def save(self, saved_tender: SavedTender) -> SavedTender:
        """Persiste una marca de interés para el workspace.

        Debe implementarse como idempotente a nivel de DB (`INSERT ... ON
        CONFLICT DO NOTHING` sobre `(supplier_id, tender_id)`): si otro
        miembro del workspace ya la había guardado, devolver la fila
        existente en vez de levantar error.
        """
        pass

    @abstractmethod
    async def delete(self, supplier_id: UUID, tender_id: UUID) -> bool:
        """Retira la marca para todo el workspace. False si no existía."""
        pass
