from datetime import datetime
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class MatchReportModel(SQLModel, table=True):
    """Reportes de mal match o de análisis incorrecto (HU-24)."""

    __tablename__ = "match_report"  # type: ignore
    # Reportar de nuevo la misma licitación reemplaza el motivo, no suma filas.
    __table_args__ = (
        UniqueConstraint(
            "supplier_id",
            "tender_id",
            "kind",
            name="uq_match_report_supplier_tender_kind",
        ),
    )

    id: UUID = Field(primary_key=True)
    supplier_id: UUID = Field(foreign_key="supplier.id", index=True)
    user_id: UUID = Field(foreign_key="users.id")
    tender_id: UUID = Field(foreign_key="tender.id", index=True)
    kind: str = Field(max_length=20)
    reason: str
    created_at: datetime


class AssistantMessageFeedbackModel(SQLModel, table=True):
    """Dislikes a mensajes del asistente, con el motivo (HU-24)."""

    __tablename__ = "assistant_message_feedback"  # type: ignore
    __table_args__ = (
        UniqueConstraint(
            "message_id", "user_id", name="uq_assistant_feedback_message_user"
        ),
    )

    id: UUID = Field(primary_key=True)
    message_id: UUID = Field(foreign_key="tender_chat_messages.id", index=True)
    user_id: UUID = Field(foreign_key="users.id")
    supplier_id: UUID | None = Field(
        default=None, foreign_key="supplier.id", index=True
    )
    tender_id: UUID = Field(foreign_key="tender.id", index=True)
    reason: str
    created_at: datetime


class AppFeedbackModel(SQLModel, table=True):
    """Comentarios, quejas y reseñas sobre el sistema, desde ajustes (HU-24)."""

    __tablename__ = "app_feedback"  # type: ignore

    id: UUID = Field(primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    kind: str = Field(max_length=20)
    message: str | None = Field(default=None)
    rating: int | None = Field(default=None)
    anonymous: bool = Field(default=False)
    created_at: datetime
