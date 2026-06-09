from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
# from uuid import UUID

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