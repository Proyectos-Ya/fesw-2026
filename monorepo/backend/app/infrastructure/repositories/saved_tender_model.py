from datetime import datetime
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class SavedTenderModel(SQLModel, table=True):
    """Modelo de base de datos para la tabla 'saved_tender' en PostgreSQL."""

    __tablename__ = "saved_tender"  # type: ignore
    # Un usuario no puede guardar dos veces la misma licitación: la constraint
    # es la garantía real de idempotencia, incluso ante peticiones simultáneas.
    __table_args__ = (
        UniqueConstraint("user_id", "tender_id", name="uq_saved_tender_user_tender"),
    )

    id: UUID = Field(primary_key=True)
    user_id: UUID = Field(
        foreign_key="users.id", index=True
    )  # Referencia al usuario dueño de la lista
    tender_id: UUID = Field(
        foreign_key="tender.id", index=True
    )  # Referencia a la licitación guardada
    saved_at: datetime  # Fecha en que el usuario la marcó como de interés
