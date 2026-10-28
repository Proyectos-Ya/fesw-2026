from abc import ABC, abstractmethod

from app.domain.entities.tender_map import TenderMapPoint


class ITenderMapRepository(ABC):
    """Lo que el mapa de licitaciones (HU-22, #314) lee de Postgres."""

    @abstractmethod
    async def list_open_with_location(
        self, region_id: int, limit: int
    ) -> tuple[list[TenderMapPoint], int]:
        """Abiertas con punto en el mapa cuyo organismo es de esa región.

        Las que cierran antes, primero. El total cuenta también las que el tope
        deja fuera.
        """
        ...
