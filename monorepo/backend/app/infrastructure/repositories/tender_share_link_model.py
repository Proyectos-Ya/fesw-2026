from datetime import datetime
from uuid import UUID

from sqlalchemy import Index
from sqlmodel import Field, SQLModel


class TenderShareLinkModel(SQLModel, table=True):
    __tablename__ = "tender_share_link"
    __table_args__ = (
        # La lista de enlaces de la ficha filtra por licitación y empresa.
        Index("ix_tender_share_link_tender_supplier", "tender_id", "supplier_id"),
    )

    id: UUID = Field(primary_key=True)
    token_hash: str = Field(max_length=64, unique=True, index=True)
    tender_id: UUID = Field(foreign_key="tender.id", ondelete="CASCADE")
    supplier_id: UUID = Field(foreign_key="supplier.id", ondelete="CASCADE")
    created_by: UUID = Field(foreign_key="users.id", ondelete="CASCADE")
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
