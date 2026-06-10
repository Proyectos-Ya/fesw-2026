from typing import List, Dict, Any
from uuid import UUID
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.services.smart_question_service import ISmartQuestionService
from app.infrastructure.repositories.question_model import QuestionModel

class SmartQuestionServiceImpl(ISmartQuestionService):
    """
    Implementacion de ISmartQuestionService.
    Utiliza un árbol de decisión como placeholder para el PMV.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_generate_questions(self, provider_id: UUID, category: str) -> List[QuestionModel]:
        clean_category = category.lower().strip()

        # Vemos si el proveedor tiene preguntas pendientes
        statement = select(QuestionModel).where(
            QuestionModel.provider_id == provider_id,
            QuestionModel.answered == False,
            QuestionModel.omitted == False
        )
        result = await self.session.exec(statement)
        existing_questions = result.all()

        # Si tiene, se retornan
        if existing_questions:
            return list(existing_questions)

        # Si la cola está vacía, generamos el pool según rubro
        questions_pool: List[Dict[str, Any]] = []

        if clean_category == "construccion":
            # Pool de preguntas estáticas para constructoras
            questions_pool = [
                {
                    "question": "¿Su empresa se encuentra actualmente inscrita en el Registro de Contratistas del MOP?",
                    "target_field": "certifications",
                    "options": ["Sí, vigente", "No", "En proceso de inscripción"]
                },
                {
                    "question": "¿Cuenta con capacidad operativa y logística para ejecutar obras civiles fuera de su región base?",
                    "target_field": "mobility",
                    "options": ["Sí, a nivel nacional", "Solo regiones contiguas", "No, solo local"]
                },
                {
                    "question": "¿Posee maquinaria pesada propia registrada con sus mantenciones al día?",
                    "target_field": "machinery",
                    "options": ["Sí, flota completa", "Solo herramientas menores", "Subcontratamos maquinaria"]
                }
            ]
        elif clean_category == "ti":
            # Pool de preguntas para servicios tecnológicos
            questions_pool = [
                {
                    "question": "¿Su software o infraestructura cuenta con certificaciones internacionales de seguridad (ej: ISO 27001)?",
                    "target_field": "security_standards",
                    "options": ["Sí, certificado", "En proceso de auditoría", "No"]
                },
                {
                    "question": "¿Tiene experiencia demostrable ejecutando integraciones con la API de Mercado Público o ClaveÚnica?",
                    "target_field": "technical_experience",
                    "options": ["Sí, múltiples proyectos", "Conocimiento teórico", "No"]
                }
            ]
        # Pueden ir más elif para otros rubros
        else:
            # Pool de preguntas generales
            questions_pool = [
                {
                    "question": "Placeholder",
                    "target_field": "Placeholder",
                    "options": ["Sí", "No", "Quizás"]
                }
            ]

        generated_questions: List[QuestionModel] = []

        # Instanciamos las preguntas en la BD para este proveedor específico
        for item in questions_pool:
            new_question = QuestionModel(
                provider_id=provider_id,
                discrepancy_type="Category_Matching",
                question=item["question"],
                target_profile_field=item["target_field"],
                target_category=clean_category,
                options=item["options"],
                answered=False,
                omitted=False
            )
            self.session.add(new_question)
            generated_questions.append(new_question)

        # flush para que postgres asign UUIDs automaticamente sin cerrar la transaccion general
        await self.session.flush()

        return generated_questions