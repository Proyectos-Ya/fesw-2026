# Ruta: app/application/useCases/smart_question_use_case.py

from uuid import UUID

from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.services.smart_question_service import ISmartQuestionService
from app.domain.entities.question import Question  # Cambiado a la entidad de dominio


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

    async def execute(self, user_id: UUID) -> list[Question]:
        """Analiza los sectores de la empresa del usuario y retorna sus preguntas.

        La empresa se resuelve desde la sesión: antes se recibía su id por query
        y no se comprobaba a quién pertenecía.
        """
        supplier = await self.supplier_repository.get_by_user_id(user_id=user_id)

        category = "general"
        if supplier and supplier.sectors:
            normalized_sectors = [str(s).lower().strip() for s in supplier.sectors]

            if (
                "construction" in normalized_sectors
                or "construcción" in normalized_sectors
            ):
                category = "construction"
            elif (
                "ti" in normalized_sectors
                or "tecnología" in normalized_sectors
                or "it" in normalized_sectors
            ):
                category = "ti"
            # Se pueden agregar otros rubros

        # La cola de preguntas se guarda por empresa. Si el usuario todavía no
        # tiene una —está en pleno onboarding—, se usa su propio id para no
        # cambiar el comportamiento anterior en ese caso. Los dos identificadores
        # son suyos: ninguno viene del cliente.
        provider_id = supplier.id if supplier else user_id

        questions = await self.smart_question_service.get_or_generate_questions(
            provider_id=provider_id, category=category
        )

        return questions
