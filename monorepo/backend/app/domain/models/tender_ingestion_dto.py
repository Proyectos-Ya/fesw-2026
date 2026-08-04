from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import List, Optional
# from uuid import UUID

from app.shared.datetime_utils import to_utc_naive

class ItemLicitacionDTO(BaseModel):
    "Mapeo de la tabla item_licitacion"
    correlativo: Optional[int] = None
    codigo_unspsc: Optional[int] = None
    codigo_categoria: Optional[str] = None
    categoria: Optional[str] = None
    nombre_producto: str
    descripcion: Optional[str] = None
    cantidad: float
    unidad_medida: str

class TenderIngestaDTO(BaseModel):
    code: str = Field(..., alias="CodigoExterno")
    name: str = Field(..., alias="Nombre")
    description: Optional[str] = Field(None, alias="Descripcion")
    status_code: int = Field(..., alias="CodigoEstado")
    published_at: datetime = Field(..., alias="FechaPublicacion")
    closing_at: datetime = Field(..., alias="FechaCierre")
    buyer_rut: str = Field(..., alias="RutComprador")
    buyer_name: str = Field(..., alias="NombreOrganismo")
    buyer_unit: str = Field(..., alias="UnidadCompra")
    region_name: str = Field(..., alias="RegionUnidad")
    
    available_amount_clp: Optional[float] = Field(None, alias="MontoEstimado")
    items: List[ItemLicitacionDTO] = []

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