from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.entities.feedback import (
    MAX_MESSAGE_CHARS,
    MAX_RATING,
    MAX_REASON_CHARS,
    MIN_RATING,
    AppFeedbackKind,
    MatchReportKind,
)


def _strip_required(value: str, error: str) -> str:
    """Recorta el texto y rechaza el que queda vacío."""
    stripped = value.strip()
    if not stripped:
        raise ValueError(error)
    return stripped


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
        return _strip_required(value, "El motivo no puede estar vacío.")


class MatchReportResponse(BaseModel):
    id: UUID
    tender_id: UUID
    kind: MatchReportKind
    reason: str
    created_at: datetime


class DislikeMessageRequest(BaseModel):
    """Cuerpo de la retroalimentación negativa (dislike) sobre una respuesta del asistente."""

    reason: str = Field(
        max_length=MAX_REASON_CHARS,
        description="Motivo del descontento o corrección sobre la respuesta del asistente.",
    )

    @field_validator("reason")
    @classmethod
    def _reason_not_blank(cls, value: str) -> str:
        return _strip_required(value, "El motivo no puede estar vacío.")


class AssistantFeedbackResponse(BaseModel):
    id: UUID
    message_id: UUID
    tender_id: UUID
    reason: str
    created_at: datetime


class CreateCommentRequest(BaseModel):
    """Cuerpo para enviar un mensaje, comentario y/o queja del sistema (HU-24, S6)."""

    message: str = Field(
        max_length=MAX_MESSAGE_CHARS,
        description="Mensaje, comentario o queja acerca del sistema.",
    )

    @field_validator("message")
    @classmethod
    def _message_not_blank(cls, value: str) -> str:
        return _strip_required(value, "El mensaje no puede estar vacío.")


class CreateReviewRequest(BaseModel):
    """Cuerpo para enviar una reseña con calificación y comentario opcional (HU-24, S7)."""

    rating: int | None = Field(
        default=None,
        ge=MIN_RATING,
        le=MAX_RATING,
        description="Cantidad de estrellas de 0 a 5.",
    )
    message: str | None = Field(
        default=None,
        max_length=MAX_MESSAGE_CHARS,
        description="Comentario opcional de la reseña.",
    )
    anonymous: bool = Field(
        default=False,
        description="Si la reseña es anónima o lleva el nombre del usuario.",
    )

    @model_validator(mode="after")
    def _exigir_estrellas_o_comentario(self) -> "CreateReviewRequest":
        msg = self.message.strip() if self.message else None
        self.message = msg or None
        if self.rating is None and self.message is None:
            raise ValueError(
                "La reseña debe incluir al menos una calificación o un comentario."
            )
        return self


class AppFeedbackResponse(BaseModel):
    id: UUID
    user_id: UUID
    kind: AppFeedbackKind
    message: str | None = None
    rating: int | None = None
    anonymous: bool = False
    created_at: datetime
