from abc import ABC, abstractmethod
from app.domain.models.tender_ingestion_dto import TenderIngestaDTO

class ITendersRepository(ABC):
    @abstractmethod
    async def save(self, tender: TenderIngestaDTO) -> None:
        # Guarda una licitacion en el sistema
        pass

    @abstractmethod
    async def exists(self, codigo_externo: str) -> bool:
        # Verificar si la licitacion ya esta ingresada
        pass