from datetime import UTC, datetime
from typing import ClassVar
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class ResultadoMatchingModel(SQLModel, table=True):
    __tablename__: ClassVar[str] = "resultado_matching"  # type: ignore

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    proveedor_id: UUID = Field(foreign_key="proveedor.id", index=True)
    licitacion_id: UUID = Field(foreign_key="licitacion.id", index=True)
    score_similitud: float
    score_reranker: float | None = Field(default=None)
    score_final: float
    version_modelo: str = Field(max_length=50)
    fecha_calculo: datetime = Field(default_factory=lambda: datetime.now(UTC))
