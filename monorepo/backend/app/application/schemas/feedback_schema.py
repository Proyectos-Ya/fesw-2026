from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.domain.entities.feedback import MAX_REASON_CHARS, MatchReportKind


class ReportMatchRequest(BaseModel):
    """Cuerpo del reporte de un mal match o de un análisis incorrecto."""

    kind: MatchReportKind = Field(
        description="`match`: la licitación no corresponde a la empresa; "
        "`analysis`: el análisis de compatibilidad es incorrecto."
    )
    reason: str = Field(
        max_length=MAX_REASON_CHARS,
        description="Por qué el usuario está disconforme. No puede ir vacío.",
    )

    @field_validator("reason")
    @classmethod
    def _reason_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("El motivo no puede estar vacío.")
        return value


class MatchReportResponse(BaseModel):
    id: UUID
    tender_id: UUID
    kind: MatchReportKind
    reason: str
    created_at: datetime
