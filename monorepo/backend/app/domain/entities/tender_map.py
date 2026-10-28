"""Ubicación de la entrega de una licitación, para el mapa de HU-22 (#314)."""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from app.shared.datetime_utils import UtcDateTime


class GeoPoint(BaseModel):
    """Un punto en el mapa, en grados decimales (WGS 84)."""

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class GeoPrecision(StrEnum):
    """Qué tan exacto es el punto guardado de una licitación.

    `comuna` es el respaldo cuando la dirección no se encontró: el punto es la
    comuna del organismo, no la dirección, y la UI lo marca como aproximado.
    `no_encontrada` es un intento sin resultado; no lleva coordenadas.
    """

    DIRECCION = "direccion"
    COMUNA = "comuna"
    NO_ENCONTRADA = "no_encontrada"


class TenderMapPoint(BaseModel):
    """Lo que el mapa necesita de una licitación: el resumen del marcador y dónde va."""

    id: UUID
    name: str
    buyer_name: str | None = None
    delivery_address: str
    closing_at: UtcDateTime
    lat: float
    lng: float
    precision: GeoPrecision


class PendingGeocoding(BaseModel):
    """Una licitación con dirección de entrega que todavía no se intentó ubicar."""

    tender_id: UUID
    delivery_address: str
    commune: str | None = None
    region: str | None = None


class CachedGeocode(BaseModel):
    """Una consulta ya respondida. `point` nulo = se preguntó y no se encontró."""

    point: GeoPoint | None = None
