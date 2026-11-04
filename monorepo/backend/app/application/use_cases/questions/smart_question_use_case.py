# Ruta: app/application/useCases/smart_question_use_case.py

from uuid import UUID

from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.services.smart_question_service import ISmartQuestionService
from app.application.use_cases.supplier.resolver_empresa import resolver_empresa
from app.domain.entities.question import Question  # Cambiado a la entidad de dominio

# Rubros de Mercado Público (`app/shared/sectors.py`) que tienen banco de preguntas
# propio en `SmartQuestionServiceImpl`. El resto usa "general". Los valores son las
# categorías que ese servicio reconoce; un test exige que cada rubro exista en
# `PRODUCT_SECTORS`.
QUESTION_CATEGORY_BY_SECTOR: dict[str, str] = {
    "Obras": "construccion",
    "Obras MINVU": "construccion",
    "Servicios de construcción y mantenimiento": "construccion",
    "Artículos para estructuras, obras y construcciones": "construccion",
    "Maquinaria para construcción y edificación": "construccion",
    "Tecnologías de la información, telecomunicaciones y radiodifusión": "ti",
    "Servicios basados en ingeniería, ciencias sociales y tecnología de la información": "ti",
}


class SmartQuestionUseCase:
    """
    Caso de Uso encargado de orquestar la obtención y generación
    de preguntas inteligentes analizando todos los sectores del Supplier.
    """

    def __init__(
        self,
        smart_question_service: ISmartQuestionService,
        supplier_repository: ISupplierRepository,
    ):
        self.smart_question_service = smart_question_service
        self.supplier_repository = supplier_repository

    async def execute(
        self, user_id: UUID, supplier_id: UUID | None = None
    ) -> list[Question]:
        """Analiza los sectores de la empresa del usuario y retorna sus preguntas.

        La empresa se resuelve desde la sesión: antes se recibía su id por query
        y no se comprobaba a quién pertenecía.
        """
        supplier = await resolver_empresa(
            self.supplier_repository, user_id=user_id, supplier_id=supplier_id
        )

        # Manda el primer rubro de la empresa que tenga banco propio, igual que
        # `categoria_de()` usa el primero de sus rubros.
        category = "general"
        if supplier and supplier.sectors:
            for sector in supplier.sectors:
                mapped = QUESTION_CATEGORY_BY_SECTOR.get(str(sector).strip())
                if mapped:
                    category = mapped
                    break

        # La cola de preguntas se guarda por empresa. Si el usuario todavía no
        # tiene una —está en pleno onboarding—, se usa su propio id para no
        # cambiar el comportamiento anterior en ese caso. Los dos identificadores
        # son suyos: ninguno viene del cliente.
        provider_id = supplier.id if supplier else user_id

        questions = await self.smart_question_service.get_or_generate_questions(
            provider_id=provider_id, category=category
        )

        return questions
