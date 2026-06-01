from typing import Optional
from pydantic import BaseModel, Field


class CrearProveedorSchema(BaseModel):
    rut: str = Field(max_length=12)
    razon_social: str = Field(max_length=255)
    nombre_fantasia: Optional[str] = Field(default=None, max_length=255)
    descripcion_libre: Optional[str] = None
    regiones: Optional[list[str]] = None
    rubros: Optional[list[str]] = None
    certificaciones: Optional[list[str]] = None
    palabras_clave: Optional[list[str]] = None
    anios_experiencia: Optional[int] = Field(default=None, ge=0)
    num_empleados: Optional[int] = Field(default=None, ge=1)