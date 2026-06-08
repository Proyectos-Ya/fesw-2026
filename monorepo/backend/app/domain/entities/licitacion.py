from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ItemLicitacion(BaseModel):
    model_config = ConfigDict(frozen=True)

    nombre: str
    descripcion: str | None = None


class Licitacion(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    codigo_externo: str
    nombre: str
    descripcion: str | None = None
    organismo_nombre: str
    monto_estimado: float | None = None
    fecha_cierre: datetime
    region: str
    estado: str
    categorias: list[str] = Field(default_factory=list)
    items: list[ItemLicitacion] = Field(default_factory=list)
    qdrant_vector_id: UUID | None = None
    version_modelo: str | None = None
    fecha_ingesta: datetime = Field(default_factory=lambda: datetime.now(UTC))
