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
        if clean_category == "construccion" or clean_category == "obras_civiles" or clean_category == "constructora":
            # Preguntas tentativas para el rubro construccion
            questions_pool = [
                {
                    "question": "¿Se encuentra su empresa inscrita en el Registro de Contratistas del Ministerio de Obras Públicas (MOP)?",
                    "target_field": "mop_registration",
                    "options": ["No", "Sí, en Segunda Categoría", "Sí, en Primera Categoría", "En proceso de inscripción"]
                },
                {
                    "question": "¿Cuenta con inscripción vigente en el Registro Nacional de Contratistas o Consultores del MINVU?",
                    "target_field": "minvu_registration",
                    "options": ["No", "Sí, en el registro de Vivienda", "Sí, en el registro de Urbanización", "Ambos"]
                },
                {
                    "question": "¿Cuál es el rango aproximado de Capital Propio acreditable de la empresa para boletas de garantía?",
                    "target_field": "financial_capacity_uf",
                    "options": ["Menos de 500 UF", "Entre 500 y 2.000 UF", "Más de 2.000 UF"]
                },
                {
                    "question": "¿Cuenta con un Experto en Prevención de Riesgos (con registro SNS) disponible en su equipo permanente?",
                    "target_field": "safety_staff",
                    "options": ["No", "Sí, Técnico en Prevención", "Sí, Ingeniero Prevencionista"]
                },
                {
                    "question": "Respecto a la maquinaria pesada necesaria para movimientos de tierra u obras viales, su empresa:",
                    "target_field": "heavy_machinery",
                    "options": ["No posee (Subcontrata)", "Cuenta con flota menor propia (Retro/Minicargadores)", "Cuenta con flota mayor propia (Excavadoras/Camiones Tolva)"]
                },
                {
                    "question": "¿Su empresa implementa o tiene certificación activa en alguna de las siguientes normas internacionales?",
                    "target_field": "iso_certifications",
                    "options": ["Ninguna", "ISO 9001 (Calidad)", "ISO 14001 o 45001 (Ambiente/Seguridad)", "Todas las anteriores"]
                },
                {
                    "question": "¿Tiene experiencia demostrable (con actas de recepción conforme) en restauración de patrimonio o monumentos?",
                    "target_field": "heritage_experience",
                    "options": ["No, solo edificación tradicional", "Sí, de 1 a 3 proyectos", "Sí, más de 3 proyectos especializados"]
                },
                {
                    "question": "¿Realiza los controles y ensayos de resistencia de materiales (hormigón/asfalto) de manera interna?",
                    "target_field": "quality_control_method",
                    "options": ["Mediante laboratorios externos certificados", "Contamos con equipamiento propio de control", "No aplica a nuestras obras"]
                },
                {
                    "question": "¿Cuál es la capacidad real de desplazamiento geográfico de sus cuadrillas operativas para la ejecución de faenas?",
                    "target_field": "operational_mobility",
                    "options": ["Solo comuna base", "Regional completo", "Interregional (Centro/Norte/Sur)", "Nacional"]
                },
                {
                    "question": "¿Tiene implementado el uso de metodologías BIM (Building Information Modeling) para revisión o cubicación?",
                    "target_field": "bim_capabilities",
                    "options": ["No, trabajamos en CAD tradicional", "Sí, nivel básico/intermedio", "Sí, modelamos proyectos complejos en BIM"]
                }
            ]
        elif clean_category == "ti":
            questions_pool = [
                {"question": "Placeholder", "target_field": "Placeholder", "options": ["Sí", "No"]},
                {"question": "Placerholder", "target_field": "Placerholder", "options": ["Sí", "No"]}
            ]
        else:
            questions_pool = [
                {
                    "question": "¿Se encuentra su empresa inscrita en el Registro de Contratistas del Ministerio de Obras Públicas (MOP)?",
                    "target_field": "mop_registration",
                    "options": ["No", "Sí, en Segunda Categoría", "Sí, en Primera Categoría", "En proceso de inscripción"]
                },
                {
                    "question": "¿Cuenta con inscripción vigente en el Registro Nacional de Contratistas o Consultores del MINVU?",
                    "target_field": "minvu_registration",
                    "options": ["No", "Sí, en el registro de Vivienda", "Sí, en el registro de Urbanización", "Ambos"]
                },
                {
                    "question": "¿Cuál es el rango aproximado de Capital Propio acreditable de la empresa para boletas de garantía?",
                    "target_field": "financial_capacity_uf",
                    "options": ["Menos de 500 UF", "Entre 500 y 2.000 UF", "Más de 2.000 UF"]
                },
                {
                    "question": "¿Cuenta con un Experto en Prevención de Riesgos (con registro SNS) disponible en su equipo permanente?",
                    "target_field": "safety_staff",
                    "options": ["No", "Sí, Técnico en Prevención", "Sí, Ingeniero Prevencionista"]
                },
                {
                    "question": "Respecto a la maquinaria pesada necesaria para movimientos de tierra u obras viales, su empresa:",
                    "target_field": "heavy_machinery",
                    "options": ["No posee (Subcontrata)", "Cuenta con flota menor propia (Retro/Minicargadores)", "Cuenta con flota mayor propia (Excavadoras/Camiones Tolva)"]
                },
                {
                    "question": "¿Su empresa implementa o tiene certificación activa en alguna de las siguientes normas internacionales?",
                    "target_field": "iso_certifications",
                    "options": ["Ninguna", "ISO 9001 (Calidad)", "ISO 14001 o 45001 (Ambiente/Seguridad)", "Todas las anteriores"]
                },
                {
                    "question": "¿Tiene experiencia demostrable (con actas de recepción conforme) en restauración de patrimonio o monumentos?",
                    "target_field": "heritage_experience",
                    "options": ["No, solo edificación tradicional", "Sí, de 1 a 3 proyectos", "Sí, más de 3 proyectos especializados"]
                },
                {
                    "question": "¿Realiza los controles y ensayos de resistencia de materiales (hormigón/asfalto) de manera interna?",
                    "target_field": "quality_control_method",
                    "options": ["Mediante laboratorios externos certificados", "Contamos con equipamiento propio de control", "No aplica a nuestras obras"]
                },
                {
                    "question": "¿Cuál es la capacidad real de desplazamiento geográfico de sus cuadrillas operativas para la ejecución de faenas?",
                    "target_field": "operational_mobility",
                    "options": ["Solo comuna base", "Regional completo", "Interregional (Centro/Norte/Sur)", "Nacional"]
                },
                {
                    "question": "¿Tiene implementado el uso de metodologías BIM (Building Information Modeling) para revisión o cubicación?",
                    "target_field": "bim_capabilities",
                    "options": ["No, trabajamos en CAD tradicional", "Sí, nivel básico/intermedio", "Sí, modelamos proyectos complejos en BIM"]
                }
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