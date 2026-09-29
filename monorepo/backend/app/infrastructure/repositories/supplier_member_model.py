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
    # `ondelete` y `server_default` repiten lo que creó la migración
    # `f1e2d3c4b5a6`: si el modelo no los declara, el siguiente
    # `alembic revision --autogenerate` propone quitarlos (PENDIENTES 3.29).
    user_id: UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    supplier_id: UUID = Field(
        foreign_key="supplier.id", ondelete="CASCADE", index=True
    )
    role: str = Field(
        default="member", index=True, sa_column_kwargs={"server_default": "member"}
    )
    status: str = Field(
        default="active", index=True, sa_column_kwargs={"server_default": "active"}
    )
    created_at: datetime
    updated_at: datetime
