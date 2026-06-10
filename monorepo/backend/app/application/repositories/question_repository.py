from abc import ABC, abstractmethod
from typing import List
from uuid import UUID
from app.domain.entities.question import Question

class IQuestionRepository(ABC):
    """Interfaz abstracta para el manejo de persistencia de preguntas."""

    @abstractmethod
    async def get_active_by_provider(self, provider_id: UUID) -> List[Question]:
        """Recupera las preguntas pendientes (no respondidas ni omitidas) de un proveedor."""
        pass

    @abstractmethod
    async def save_all(self, questions: List[Question]) -> List[Question]:
        """Persiste un listado de preguntas en la base de datos."""
        pass