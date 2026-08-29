from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Column, Index, UniqueConstraint
from sqlmodel import Field, SQLModel


class NotificationPreferenceModel(SQLModel, table=True):
    """Preferencias de alertas, una fila por usuario."""

    __tablename__ = "notification_preference"  # type: ignore

    id: UUID = Field(primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True, unique=True)
    enabled: bool = Field(default=True)
    threshold: float = Field(default=0.70)  # Escala 0..1, igual que final_score
    delivery_mode: str = Field(default="immediate")  # immediate | daily_digest
    email_delivery_enabled: bool = Field(default=True)
    last_failure_reason: str | None = Field(default=None)
    last_failure_at: datetime | None = Field(default=None)
    created_at: datetime
    updated_at: datetime


class NotificationModel(SQLModel, table=True):
    """Aviso in-app de una licitación compatible."""

    __tablename__ = "notification"  # type: ignore

    __table_args__ = (
        # Doble función: evita mostrar el mismo aviso dos veces y, sobre todo,
        # es el registro de "ya notifiqué esta licitación a este usuario" que
        # consulta el escaneo. Sin esta constraint, cada ciclo del scheduler
        # volvería a avisar de lo mismo.
        UniqueConstraint("user_id", "tender_id", name="uq_notification_user_tender"),
        # El contador de la campanita filtra por usuario y no leídos.
        Index("ix_notification_user_read", "user_id", "read_at"),
    )

    id: UUID = Field(primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    tender_id: UUID = Field(foreign_key="tender.id", index=True)
    score: float  # Score congelado al momento de generar el aviso
    read_at: datetime | None = Field(default=None)
    created_at: datetime


class NotificationDeliveryModel(SQLModel, table=True):
    """Cola de salida de los correos de alerta."""

    __tablename__ = "notification_delivery"  # type: ignore

    __table_args__ = (
        # El loop de entrega barre por estado y fecha del próximo intento.
        Index("ix_notification_delivery_pendientes", "status", "next_attempt_at"),
    )

    id: UUID = Field(primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    kind: str = Field(default="immediate")  # immediate | digest
    # Lista de avisos que cubre este correo: uno en el envío inmediato, varios
    # en el resumen diario. Va como JSON y no como tabla puente porque nunca se
    # consulta en la dirección contraria.
    notification_ids: list[str] | None = Field(default=None, sa_column=Column(JSON))
    status: str = Field(default="pending")  # pending | sent | failed_permanent
    attempts: int = Field(default=0)
    last_error: str | None = Field(default=None)
    next_attempt_at: datetime
    sent_at: datetime | None = Field(default=None)
    created_at: datetime
