from abc import ABC, abstractmethod

from app.domain.entities.tender_map import GeoPoint


class IGeocodingService(ABC):
    """Traduce una dirección escrita a un punto en el mapa (HU-22, #314).

    `None` es que la fuente respondió y no encontró nada. Si la fuente está
    caída, se lanza `GeocodingUnavailable`.
    """

    @abstractmethod
    async def geocode(self, query: str) -> GeoPoint | None:
        """Ubica `query`, una dirección completa como "Calle 123, Comuna, Región, Chile"."""
