from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Proveedor(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    rut: str
    razon_social: str
    nombre_fantasia: Optional[str] = None
    descripcion_libre: Optional[str] = None
    regiones: Optional[list[str]] = None
    rubros: Optional[list[str]] = None
    certificaciones: Optional[list[str]] = None
    palabras_clave: Optional[list[str]] = None
    anios_experiencia: Optional[int] = None
    num_empleados: Optional[int] = None
    fecha_creacion: datetime = Field(default_factory=datetime.utcnow)
    fecha_actualizacion: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        frozen = True  # entidad inmutable, los cambios generan una nueva instancia