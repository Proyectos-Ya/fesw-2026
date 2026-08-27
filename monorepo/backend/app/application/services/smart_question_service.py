from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.question import Question


class ISmartQuestionService(ABC):
    """
    Interfaz abstracta para el servicio de preguntas inteligentes.
    """

    @abstractmethod
    async def get_or_generate_questions(
        self, provider_id: UUID, category: str
    ) -> list[Question]:
        """
        Recupera las preguntas pendientes en la BD.
        Si la cola esta vacia, triggerea la logica para poblar el arbol segun categoria
        """
        pass
