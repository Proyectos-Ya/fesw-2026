"""Entidades del dominio de alertas de licitaciones (HdU 08).

Tres piezas con responsabilidades separadas a propósito:

* `NotificationPreference` — qué quiere recibir el usuario y por qué canal.
* `Notification` — el aviso en sí, que además hace de registro de "ya avisé de
  esta licitación": sin él, cada escaneo volvería a notificar lo mismo.
* `NotificationDelivery` — el intento de entrega por correo, con su estado y su
  reintento. Está separado del aviso porque un resumen diario agrupa varios
  avisos en un solo correo, y porque el aviso in-app existe aunque el correo
  falle.
"""

from datetime import timedelta
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from app.shared.constants import HIGH_COMPATIBILITY_THRESHOLD
from app.shared.datetime_utils import UtcDateTime, utc_now_naive

DeliveryMode = Literal["immediate", "daily_digest"]
DeliveryKind = Literal["immediate", "digest"]
DeliveryStatus = Literal["pending", "sent", "failed_permanent"]

# Tope del backoff exponencial. Sin él, unos pocos fallos seguidos empujarían el
# siguiente intento a días de distancia y el correo no saldría nunca.
MAX_RETRY_BACKOFF_MINUTES = 60


class NotificationPreference(BaseModel):
    """Preferencias de alertas de un usuario.

    `threshold` va en la escala 0..1 de `MatchingResult.final_score`, no en
    porcentaje: la conversión a "70%" ocurre solo en la interfaz.
    """

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    enabled: bool = True
    threshold: float = HIGH_COMPATIBILITY_THRESHOLD
    delivery_mode: DeliveryMode = "immediate"
    # Se apaga solo cuando el proveedor de correo rechaza la dirección de forma
    # definitiva. El aviso in-app sigue funcionando; lo único que se corta es el
    # correo, y el usuario puede reactivarlo tras corregir su dirección.
    email_delivery_enabled: bool = True
    last_failure_reason: str | None = None
    last_failure_at: UtcDateTime | None = None
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)
    updated_at: UtcDateTime = Field(default_factory=utc_now_naive)

    @field_validator("threshold")
    @classmethod
    def validate_threshold(cls, value: float) -> float:
        """Un umbral de 0 avisaría de todo y uno mayor que 1 no avisaría nunca."""
        if not 0 < value <= 1:
            raise ValueError("El umbral debe estar en el rango (0, 1]")
        return value

    def wants_email(self) -> bool:
        """Si corresponde intentar el envío por correo para este usuario."""
        return self.enabled and self.email_delivery_enabled


class Notification(BaseModel):
    """Aviso in-app de una licitación compatible.

    La unicidad de `(user_id, tender_id)` la garantiza la base de datos; acá
    solo se modela el aviso.
    """

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    tender_id: UUID
    # Score que tenía el match cuando se generó el aviso. Se congela a propósito:
    # el pipeline recalcula y el número puede moverse, pero el aviso debe seguir
    # explicando por qué se envió.
    score: float
    read_at: UtcDateTime | None = None
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    def mark_read(self) -> None:
        if self.read_at is None:
            self.read_at = utc_now_naive()


class NotificationDelivery(BaseModel):
    """Intento de entrega por correo de uno o varios avisos.

    Es la cola de salida: mientras `status` sea `pending`, el loop de entrega la
    vuelve a tomar cuando `next_attempt_at` ya pasó.
    """

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    kind: DeliveryKind = "immediate"
    notification_ids: list[UUID] = Field(default_factory=list)
    status: DeliveryStatus = "pending"
    attempts: int = 0
    last_error: str | None = None
    next_attempt_at: UtcDateTime = Field(default_factory=utc_now_naive)
    sent_at: UtcDateTime | None = None
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)

    def is_due(self, now: UtcDateTime) -> bool:
        """Si toca intentar la entrega ahora."""
        return self.status == "pending" and self.next_attempt_at <= now

    def mark_sent(self, now: UtcDateTime) -> None:
        self.status = "sent"
        self.sent_at = now
        self.last_error = None

    def register_transient_failure(self, reason: str, now: UtcDateTime) -> None:
        """Deja la entrega pendiente y aleja el siguiente intento.

        Backoff exponencial en minutos (2, 4, 8, ...) con tope, para no golpear
        un servicio caído en cada ciclo del loop.
        """
        self.attempts += 1
        self.last_error = reason
        espera = min(2**self.attempts, MAX_RETRY_BACKOFF_MINUTES)
        self.next_attempt_at = now + timedelta(minutes=espera)

    def mark_failed_permanent(self, reason: str, now: UtcDateTime) -> None:
        """Cierra la entrega: la dirección no existe y reintentar no ayudaría."""
        self.attempts += 1
        self.status = "failed_permanent"
        self.last_error = reason
        self.next_attempt_at = now
