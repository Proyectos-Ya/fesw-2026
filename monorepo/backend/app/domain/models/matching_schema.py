from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.entities.matching_result import MatchingResult as ResultadoMatching


class MatchRequest(BaseModel):
    proveedor_id: UUID
    top_k: int = Field(default=10, ge=1)
    region: str | None = None
    monto_min: float | None = None


class MatchResult(BaseModel):
    resultados: list[ResultadoMatching]
    version_modelo: str


class ObtenerScoreRequest(BaseModel):
    proveedor_id: UUID
    licitacion_id: UUID
