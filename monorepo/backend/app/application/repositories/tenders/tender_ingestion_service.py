from abc import ABC, abstractmethod
from typing import List
from monorepo.backend.app.domain.models.tender_ingestion_dto import TenderIngestaDTO

class TenderIngestionService(ABC):
    @abstractmethod
    async def fetch_public_tenders(self) -> List[TenderIngestaDTO]:
        # Define la logica para pegarle a la API de Mercado Público y retornar los datos limpios en DTOs
        pass