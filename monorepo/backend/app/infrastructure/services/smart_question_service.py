from typing import List, Dict, Any
from uuid import UUID
from app.application.services.smart_question_service import ISmartQuestionService
from app.application.repositories.question_repository import IQuestionRepository
from app.domain.entities.question import Question

class SmartQuestionServiceImpl(ISmartQuestionService):
    """Servicio encargado puramente de la lógica/heurística del árbol del PMV."""

    def __init__(self, question_repository: IQuestionRepository):
        self.question_repository = question_repository

    async def get_or_generate_questions(self, provider_id: UUID, category: str) -> List[Question]:
        clean_category = category.lower().strip()

        # El repositorio se encarga de la query SQL
        existing_questions = await self.question_repository.get_active_by_provider(provider_id)
        if existing_questions:
            return existing_questions

        # Logica del arbol
        questions_pool: List[Dict[str, Any]] = []
        if clean_category == "construction":
            questions_pool = [
                {"question": "¿Inscrito en el Registro de Contratistas del MOP?", "target_field": "certifications", "options": ["Sí", "No"]},
                {"question": "¿Capacidad logística fuera de su región base?", "target_field": "mobility", "options": ["Sí", "No"]}
            ]
        elif clean_category == "Seguridad":
            questions_pool = [
                {"question": "Placeholder", "target_field": "Placeholder", "options": ["Sí", "No"]},
                {"question": "Placerholder", "target_field": "Placerholder", "options": ["Sí", "No"]}
            ]
        else:
            questions_pool = [
                {"question": "Placeholder", "target_field": "Placerholder", "options": ["Sí", "No"]}
            ]

        generated_entities: List[Question] = []
        for item in questions_pool:
            new_question = Question(
                provider_id=provider_id,
                question=str(item["question"]),
                target_profile_field=str(item["target_field"]),
                target_category=clean_category,
                options=list(item["options"])
            )
            generated_entities.append(new_question)

        # 3. Le pasamos el saco de entidades al repositorio para que las guarde
        return await self.question_repository.save_all(generated_entities)