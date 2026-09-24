from datetime import datetime
from uuid import UUID

from sqlmodel import Field, SQLModel


class SupplierInvitationModel(SQLModel, table=True):
    """Modelo de base de datos para invitaciones a espacios de trabajo."""

    __tablename__ = "supplier_invitations"  # type: ignore

    id: UUID = Field(primary_key=True)
    supplier_id: UUID = Field(foreign_key="supplier.id", index=True)
    email: str = Field(index=True)
    role: str = Field(default="member")
    invited_by_user_id: UUID = Field(foreign_key="users.id", index=True)
    token: str = Field(unique=True, index=True)
    status: str = Field(default="pending", index=True)
    expires_at: datetime
    created_at: datetime
    accepted_at: datetime | None = None
