from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# from uuid import UUID
from app.shared.datetime_utils import to_utc_naive


class ItemLicitacionDTO(BaseModel):
    "Mapeo de la tabla item_licitacion"

    correlativo: int | None = None
    codigo_unspsc: int | None = None
    codigo_categoria: str | None = None
    categoria: str | None = None
    nombre_producto: str
    descripcion: str | None = None
    cantidad: float
    unidad_medida: str


class TenderIngestaDTO(BaseModel):
    code: str = Field(..., alias="CodigoExterno")
    name: str = Field(..., alias="Nombre")
    description: str | None = Field(None, alias="Descripcion")
    status_code: int = Field(..., alias="CodigoEstado")
    published_at: datetime = Field(..., alias="FechaPublicacion")
    closing_at: datetime = Field(..., alias="FechaCierre")
    buyer_rut: str = Field(..., alias="RutComprador")
    buyer_name: str = Field(..., alias="NombreOrganismo")
    buyer_unit: str = Field(..., alias="UnidadCompra")
    region_name: str = Field(..., alias="RegionUnidad")

    available_amount_clp: float | None = Field(None, alias="MontoEstimado")
    items: list[ItemLicitacionDTO] = []

    class Config:
        populate_by_name = True

    @field_validator("published_at", "closing_at", mode="after")
    @classmethod
    def normalize_to_utc(cls, value: datetime) -> datetime:
        """Mercado Público entrega estas fechas en hora local de Chile y sin
        offset. Se normalizan a UTC naive aquí, en el borde de entrada, para que
        toda la base de datos comparta una única zona horaria."""
        normalized = to_utc_naive(value)
        assert normalized is not None  # el campo es obligatorio, nunca es None
        return normalized
