from uuid import UUID

from app.application.repositories.question_repository import IQuestionRepository
from app.application.services.smart_question_service import ISmartQuestionService
from app.domain.entities.question import Question


class SmartQuestionServiceImpl(ISmartQuestionService):
    """Servicio encargado de recuperar las preguntas inteligentes activas del proveedor.

    Las preguntas son generadas exclusivamente por la IA a partir del análisis
    profundo de licitaciones (GenerateTenderSmartQuestionsUseCase) y se persisten
    en el repositorio de preguntas. No se generan preguntas estáticas.
    """

    def __init__(self, question_repository: IQuestionRepository):
        self.question_repository = question_repository

    async def get_or_generate_questions(
        self, provider_id: UUID, category: str = "general"
    ) -> list[Question]:
        return await self.question_repository.get_active_by_provider(provider_id)
