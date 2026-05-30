from datetime import datetime
from typing import ClassVar, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, TEXT
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import declared_attr
from sqlmodel import Field, SQLModel


class ProveedorModel(SQLModel, table=True):
    @declared_attr
    def __tablename__(cls) -> str:
        return "proveedor"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    rut: str = Field(unique=True, max_length=12)
    razon_social: str = Field(max_length=255)
    nombre_fantasia: Optional[str] = Field(default=None, max_length=255)
    descripcion_libre: Optional[str] = Field(default=None)
    regiones: Optional[list[str]] = Field(default=None, sa_column=Column(ARRAY(TEXT)))
    rubros: Optional[list[str]] = Field(default=None, sa_column=Column(ARRAY(TEXT)))
    certificaciones: Optional[list[str]] = Field(default=None, sa_column=Column(ARRAY(TEXT)))
    palabras_clave: Optional[list[str]] = Field(default=None, sa_column=Column(ARRAY(TEXT)))
    anios_experiencia: Optional[int] = Field(default=None, ge=0)
    num_empleados: Optional[int] = Field(default=None, ge=1)
    fecha_creacion: datetime = Field(default_factory=datetime.utcnow)
    fecha_actualizacion: datetime = Field(default_factory=datetime.utcnow)