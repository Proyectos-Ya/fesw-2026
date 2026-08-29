from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.saved_tender import SavedTender


class ISavedTenderRepository(ABC):
    """Interfaz abstracta para la persistencia de las licitaciones guardadas por un usuario."""

    @abstractmethod
    async def get_by_user_id(self, user_id: UUID) -> list[SavedTender]:
        """Obtiene todas las licitaciones que el usuario marcó como de interés."""
        pass

    @abstractmethod
    async def get(self, user_id: UUID, tender_id: UUID) -> SavedTender | None:
        """Obtiene la marca de interés de un usuario sobre una licitación, si existe."""
        pass

    @abstractmethod
    async def save(self, saved_tender: SavedTender) -> SavedTender:
        """Persiste una nueva marca de interés."""
        pass

    @abstractmethod
    async def delete(self, user_id: UUID, tender_id: UUID) -> bool:
        """Elimina la marca de interés. Retorna False si no existía."""
        pass
