from abc import ABC, abstractmethod
from typing import List
from app.domain.models.tender_ingestion_dto import TenderIngestaDTO

class ITenderIngestionService(ABC):
    """
    Interfaz para el servicio de obtención de datos externos.
    Se ubica en application/services/tenders.
    """
    @abstractmethod
    async def fetch_public_tenders(self) -> List[TenderIngestaDTO]:
        """
        Define la lógica para pegarle a la API de Mercado Público 
        y retornar los datos limpios en DTOs.
        """
        pass