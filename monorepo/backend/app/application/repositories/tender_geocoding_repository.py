from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.tender_map import (
    CachedGeocode,
    GeoPoint,
    GeoPrecision,
    PendingGeocoding,
)


class ITenderGeocodingRepository(ABC):
    """Lo que la cola de geocodificación (#314) necesita de Postgres, y nada más.

    Interfaz aparte de `ITenderRepository`, como `ITenderStatusSyncRepository`:
    esa ya es ancha y cada método nuevo obliga a tocar todos sus dobles.
    """

    @abstractmethod
    async def list_pending(self, limit: int) -> list[PendingGeocoding]:
        """Abiertas con dirección de entrega y sin intento, las que cierran antes primero."""
        ...

    @abstractmethod
    async def save_location(
        self, tender_id: UUID, point: GeoPoint | None, precision: GeoPrecision
    ) -> None:
        """Guarda el resultado y la hora del intento, sin mover `updated_at`."""
        ...

    @abstractmethod
    async def get_cached(self, query: str) -> CachedGeocode | None:
        """La respuesta guardada de esa consulta, o `None` si nunca se hizo."""
        ...

    @abstractmethod
    async def cache(self, query: str, point: GeoPoint | None) -> None:
        """Guarda la respuesta de una consulta, también cuando no encontró nada."""
        ...
