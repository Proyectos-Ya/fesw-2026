from app.application.tenders.interfaces.tender_ingestion_service import TenderIngestionService
from app.application.tenders.interfaces.tenders_repository import ITendersRepository
from typing import Dict, Any

class TenderIngestionUseCase:
    def __init__(self, 
                ingestion_service: TenderIngestionService,
                repository: ITendersRepository,
    ): 
        self.ingestion_service = ingestion_service
        self.repository = repository

    async def execute(self) -> Dict[str, Any]:
        # Obtener licitaciones de la API
        tenders_dto = await self.ingestion_service.fetch_public_tenders()
        count_saved = 0

        # Guardar sin duplicados
        for tender in tenders_dto:
            if not await self.repository.exists(tender.codigo_externo):
                await self.repository.save(tender)
                count_saved += 1

        return {"status": "success", "fetched": len(tenders_dto), "count": count_saved}