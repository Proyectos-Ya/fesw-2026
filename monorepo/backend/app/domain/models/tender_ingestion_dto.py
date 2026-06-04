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
    "Mapeo de la tabla licitacion"
    codigo_externo: str = Field(..., alias="CodigoExterno")
    nombre: str = Field(..., alias="Nombre")
    descripcion: Optional[str] = Field(None, alias="Descripcion")
    estado: Optional[str] = Field(None, alias="Estado")
    codigo_estado: Optional[int] = Field(None, alias="CodigoEstado")
    tipo: Optional[int] = Field(None, alias="Tipo")
    monto_estimado: Optional[float] = Field(None, alias="MontoEstimado")
    organismo_codigo: Optional[str] = Field(None, alias="CodigoOrganismo")
    organismo_nombre: Optional[str] = Field(None, alias="NombreOrganismo")
    region: Optional[str] = Field(None, alias="Region")
    comuna: Optional[str] = Field(None, alias="Comuna")
    es_obra: bool = False
    es_renovable: bool = False
    fecha_publicacion: Optional[datetime] = Field(None, alias="FechaPublicacion")
    fecha_cierre: Optional[datetime] = Field(None, alias="FechaCierre")
    fecha_adjudicacion: Optional[datetime] = Field(None, alias="FechaAdjudicacion")
    
    # Relacion con items
    items: List[ItemLicitacionDTO] = []

    class Config:
        populate_by_name = True