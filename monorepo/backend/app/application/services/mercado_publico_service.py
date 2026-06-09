from abc import ABC, abstractmethod

from app.domain.entities.tender import Tender as Licitacion


class IMercadoPublicoService(ABC):
    """
    Contrato para obtener licitaciones desde la API de Mercado Público.
    La implementación de infraestructura es responsable de mapear la
    respuesta cruda del API a entidades Licitacion del dominio.
    """

    @abstractmethod
    async def fetch_licitaciones(
        self,
        estado: str,
        limit: int,
        offset: int,
    ) -> list[Licitacion]: ...
