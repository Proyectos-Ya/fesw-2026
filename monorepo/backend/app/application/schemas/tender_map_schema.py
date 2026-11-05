from pydantic import BaseModel

from app.domain.entities.tender_map import TenderMapPoint


class TenderMapResponse(BaseModel):
    """Marcadores del mapa de licitaciones de una región (HU-22, #314).

    Como en la búsqueda, `total` cuenta todas las que cumplen y `is_truncated`
    avisa que el tope dejó marcadores fuera.
    """

    region: str
    items: list[TenderMapPoint]
    total: int
    is_truncated: bool = False
