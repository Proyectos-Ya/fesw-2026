from datetime import datetime
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class SupplierMemberModel(SQLModel, table=True):
    """Modelo de base de datos para membresías entre usuarios y empresas."""

    __tablename__ = "supplier_members"  # type: ignore
    __table_args__ = (
        UniqueConstraint(
            "user_id", "supplier_id", name="uq_supplier_member_user_supplier"
        ),
    )

    id: UUID = Field(primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    supplier_id: UUID = Field(foreign_key="supplier.id", index=True)
    role: str = Field(default="member", index=True)
    status: str = Field(default="active", index=True)
    created_at: datetime
    updated_at: datetime
