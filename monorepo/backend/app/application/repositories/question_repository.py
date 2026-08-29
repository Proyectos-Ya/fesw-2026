from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.question import Question


class IQuestionRepository(ABC):
    """Interfaz abstracta para el manejo de persistencia de preguntas."""

    @abstractmethod
    async def get_active_by_provider(self, provider_id: UUID) -> list[Question]:
        """Recupera las preguntas pendientes (no respondidas ni omitidas) de un proveedor."""
        pass

    @abstractmethod
    async def save_all(self, questions: list[Question]) -> list[Question]:
        """Persiste un listado de preguntas en la base de datos."""
        pass
