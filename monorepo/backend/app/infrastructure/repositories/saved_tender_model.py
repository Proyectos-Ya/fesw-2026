from datetime import datetime
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class SavedTenderModel(SQLModel, table=True):
    """Modelo de base de datos para la tabla 'saved_tender' (HU-18).

    Scoping por workspace: la unicidad activa es `(supplier_id, tender_id)`.
    `user_id` queda como auditoría ("quién la guardó primero").
    """

    __tablename__ = "saved_tender"  # type: ignore
    __table_args__ = (
        UniqueConstraint(
            "supplier_id", "tender_id", name="uq_saved_tender_supplier_tender"
        ),
    )

    id: UUID = Field(primary_key=True)
    supplier_id: UUID = Field(foreign_key="supplier.id", index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    tender_id: UUID = Field(foreign_key="tender.id", index=True)
    saved_at: datetime
