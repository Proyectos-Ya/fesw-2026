"""Retroalimentación de usuario (HU-24, #315).

Tres cosas distintas que comparten el mismo objetivo —que la empresa le diga al
sistema qué anduvo mal—, pero que se guardan y se usan por separado:

- `MatchReport`: la empresa reporta un mal match o un análisis de
  compatibilidad incorrecto sobre una licitación.
- `AssistantMessageFeedback`: dislike a un mensaje del asistente, con su motivo.
- `AppFeedback`: comentario/queja o reseña sobre el sistema, desde ajustes.
"""

from enum import StrEnum
from typing import Self
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from app.shared.datetime_utils import UtcDateTime, utc_now_naive

MAX_REASON_CHARS = 1000
MAX_MESSAGE_CHARS = 2000
MIN_RATING = 0
MAX_RATING = 5


def _clean(value: str | None, max_chars: int, field: str) -> str | None:
    """Recorta espacios y valida el largo; un texto vacío queda como `None`."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) > max_chars:
        raise ValueError(f"{field} no puede superar los {max_chars} caracteres.")
    return value


class MatchReportKind(StrEnum):
    # El match recomendado es malo: la licitación deja de recomendarse.
    MATCH = "match"
    # El análisis de compatibilidad es incorrecto: se registra, no oculta nada.
    ANALYSIS = "analysis"


class MatchReport(BaseModel):
    """Reporte de una empresa sobre una licitación, único por (empresa, licitación, tipo)."""

    id: UUID = Field(default_factory=uuid4)
    supplier_id: UUID
    user_id: UUID
    tender_id: UUID
    kind: MatchReportKind
    reason: str
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)

    @field_validator("reason")
    @classmethod
    def _reason(cls, value: str) -> str:
        cleaned = _clean(value, MAX_REASON_CHARS, "El motivo")
        if cleaned is None:
            raise ValueError("El motivo no puede estar vacío.")
        return cleaned


class AssistantMessageFeedback(BaseModel):
    """Dislike de un usuario a un mensaje del asistente, único por (mensaje, usuario)."""

    id: UUID = Field(default_factory=uuid4)
    message_id: UUID
    user_id: UUID
    # Nulo si no se pudo resolver la empresa activa al preguntar.
    supplier_id: UUID | None = None
    tender_id: UUID
    reason: str
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)

    @field_validator("reason")
    @classmethod
    def _reason(cls, value: str) -> str:
        cleaned = _clean(value, MAX_REASON_CHARS, "El motivo")
        if cleaned is None:
            raise ValueError("El motivo no puede estar vacío.")
        return cleaned


class AppFeedbackKind(StrEnum):
    COMMENT = "comment"  # mensaje, comentario o queja
    REVIEW = "review"  # estrellas (0-5) y/o comentario


class AppFeedback(BaseModel):
    """Mensaje o reseña sobre el sistema.

    `anonymous` solo decide si el nombre se muestra: el `user_id` se guarda
    siempre para poder responderle al usuario.
    """

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    kind: AppFeedbackKind
    message: str | None = None
    rating: int | None = None
    anonymous: bool = False
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)

    @field_validator("message")
    @classmethod
    def _message(cls, value: str | None) -> str | None:
        return _clean(value, MAX_MESSAGE_CHARS, "El mensaje")

    @field_validator("rating")
    @classmethod
    def _rating(cls, value: int | None) -> int | None:
        if value is not None and not MIN_RATING <= value <= MAX_RATING:
            raise ValueError(
                f"Las estrellas van de {MIN_RATING} a {MAX_RATING}."
            )
        return value

    @model_validator(mode="after")
    def _rules_by_kind(self) -> Self:
        if self.kind is AppFeedbackKind.COMMENT:
            if self.message is None:
                raise ValueError("El mensaje no puede estar vacío.")
            if self.rating is not None:
                raise ValueError("Un comentario no lleva estrellas.")
        elif self.rating is None and self.message is None:
            raise ValueError("La reseña necesita estrellas, un comentario o ambos.")
        return self
