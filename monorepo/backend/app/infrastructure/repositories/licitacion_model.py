from datetime import UTC, datetime
from typing import ClassVar
from uuid import UUID, uuid4

from sqlalchemy import TEXT, Column
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field, SQLModel


class LicitacionModel(SQLModel, table=True):
    __tablename__: ClassVar[str] = "licitacion"  # type: ignore

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    codigo_externo: str = Field(unique=True, max_length=50)
    nombre: str = Field(max_length=500)
    descripcion: str | None = Field(default=None)
    organismo_nombre: str = Field(max_length=255)
    monto_estimado: float | None = Field(default=None)
    fecha_cierre: datetime
    region: str = Field(max_length=100)
    estado: str = Field(max_length=50)
    categorias: list[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(TEXT), nullable=False),
    )
    items: list = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False),
    )
    qdrant_vector_id: UUID | None = Field(default=None)
    version_modelo: str | None = Field(default=None, max_length=50)
    fecha_ingesta: datetime = Field(default_factory=lambda: datetime.now(UTC))
