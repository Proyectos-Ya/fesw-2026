from monorepo.backend.app.application.repositories.tender_ingestion_service import TenderIngestionService
from monorepo.backend.app.application.repositories.tenders_repository import ITendersRepository
from typing import Dict, Any

class TenderIngestionUseCase:
    def __init__(self, 
                ingestion_service: TenderIngestionService,
                repository: ITendersRepository,
    ): 
        self.ingestion_service = ingestion_service
        self.repository = repository

    async def execute(self, limit: int | None = None) -> Dict[str, Any]:
        # Obtener licitaciones de la API
        tenders_dto = await self.ingestion_service.fetch_public_tenders()
        # Tenemos un limite para casos de prueba durante el desarrollo
        if limit is not None:
            tenders_dto = tenders_dto[:limit]
            print(f"[Dev Mode] Límite aplicado: procesando solo {len(tenders_dto)} licitaciones.")

        count_saved = 0
        # Guardar sin duplicados
        for tender in tenders_dto:
            if not await self.repository.exists(tender.codigo_externo):
                await self.repository.save(tender)
                count_saved += 1

        return {"status": "success", "fetched": len(tenders_dto), "count": count_saved}