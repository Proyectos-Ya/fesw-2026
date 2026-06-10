from abc import ABC, abstractmethod
from typing import List
from uuid import UUID
from app.infrastructure.repositories.question_model import QuestionModel

class ISmartQuestionService(ABC):
    """
    Interfaz abstracta para el servicio de preguntas inteligentes.
    """
    @abstractmethod
    async def get_or_generate_questions(self, provider_id: UUID, category: str) -> List[QuestionModel]:
        """
        Recupera las preguntas pendientes en la BD.
        Si la cola esta vacia, triggerea la logica para poblar el arbol segun categoria
        """
        pass