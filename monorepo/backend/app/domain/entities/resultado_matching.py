from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ResultadoMatching(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    proveedor_id: UUID
    licitacion_id: UUID
    score_similitud: float
    score_reranker: float | None = None
    score_final: float
    version_modelo: str
    fecha_calculo: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
