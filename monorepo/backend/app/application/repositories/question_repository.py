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
    async def get_by_id(self, question_id: UUID) -> Question | None:
        """Recupera una pregunta por su id único."""
        pass

    @abstractmethod
    async def get_by_provider_and_tender(
        self, provider_id: UUID, tender_id: UUID
    ) -> list[Question]:
        """Recupera todas las preguntas asociadas a un proveedor y una licitación."""
        pass

    @abstractmethod
    async def save(self, question: Question) -> Question:
        """Persiste una pregunta individual."""
        pass

    @abstractmethod
    async def save_all(self, questions: list[Question]) -> list[Question]:
        """Persiste un listado de preguntas en la base de datos."""
        pass

    @abstractmethod
    async def update(self, question: Question) -> Question:
        """Actualiza una pregunta existente."""
        pass
