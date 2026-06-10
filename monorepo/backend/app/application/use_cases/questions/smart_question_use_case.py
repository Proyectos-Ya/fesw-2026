# Ruta: app/application/useCases/smart_question_use_case.py

from typing import List
from uuid import UUID
from app.application.services.smart_question_service import ISmartQuestionService
from app.domain.entities.question import Question  # Cambiado a la entidad de dominio
from app.application.repositories.supplier_repository import ISupplierRepository 

class SmartQuestionUseCase:
    """
    Caso de Uso encargado de orquestar la obtención y generación 
    de preguntas inteligentes analizando todos los sectores del Supplier.
    """

    def __init__(
        self, 
        smart_question_service: ISmartQuestionService,
        supplier_repository: ISupplierRepository
    ):
        self.smart_question_service = smart_question_service
        self.supplier_repository = supplier_repository

    async def execute(self, provider_id: UUID) -> List[Question]:
        """
        Busca al proveedor por ID, analiza sus sectores y retorna las entidades de dominio.
        """
        supplier = await self.supplier_repository.get_by_id(supplier_id=provider_id)
        
        category = "general"
        if supplier and supplier.sectors:
            normalized_sectors = [str(s).lower().strip() for s in supplier.sectors]
            
            if "construction" in normalized_sectors or "construcción" in normalized_sectors:
                category = "construction"
            elif "ti" in normalized_sectors or "tecnología" in normalized_sectors or "it" in normalized_sectors:
                category = "ti"
            # Se pueden agregar otros rubros

        questions = await self.smart_question_service.get_or_generate_questions(
            provider_id=provider_id, 
            category=category
        )
        
        return questions
