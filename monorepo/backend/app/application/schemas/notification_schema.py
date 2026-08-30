"""Esquemas HTTP de las alertas de licitaciones.

El umbral viaja al frontend en porcentaje (0–100) porque es lo que el usuario
elige en pantalla; la base y el dominio siguen guardando la escala 0..1 de
`final_score`. La conversión ocurre solo en este borde.
"""

from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.entities.tender import Tender
from app.shared.datetime_utils import UtcDateTime


class NotificationPreferenceResponse(BaseModel):
    enabled: bool
    threshold_pct: int = Field(
        description="Umbral de compatibilidad en porcentaje (1–100)"
    )
    delivery_mode: str
    email_delivery_enabled: bool
    last_failure_reason: str | None = None
    last_failure_at: UtcDateTime | None = None


class UpdateNotificationPreferencesRequest(BaseModel):
    enabled: bool | None = None
    threshold_pct: int | None = Field(default=None, ge=1, le=100)
    delivery_mode: str | None = Field(
        default=None, description="'immediate' o 'daily_digest'"
    )
    reactivate_email: bool = False


class NotificationResponse(BaseModel):
    id: UUID
    tender_id: UUID
    score_pct: int
    read_at: UtcDateTime | None = None
    created_at: UtcDateTime
    # `True` también cuando la licitación desapareció de la base: en ambos casos
    # lo que corresponde mostrar es que ya no se puede postular.
    is_closed: bool
    tender: Tender | None = None


class UnreadCountResponse(BaseModel):
    count: int


class MarkAllReadResponse(BaseModel):
    updated: int


class NotificationDeliveryResponse(BaseModel):
    """Una fila de la bandeja de salida.

    Es la evidencia visible de que un correo quedó pendiente y se reintenta.
    """

    id: UUID
    kind: str
    status: str
    attempts: int
    last_error: str | None = None
    next_attempt_at: UtcDateTime
    sent_at: UtcDateTime | None = None
    created_at: UtcDateTime
    notification_ids: list[UUID] = Field(default_factory=list)


class TenderDetailResponse(BaseModel):
    """Ficha de licitación, abierta o cerrada."""

    tender: Tender
    score_pct: int | None = None
    is_closed: bool
