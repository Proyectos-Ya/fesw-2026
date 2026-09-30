from datetime import datetime
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class SupplierInvitationModel(SQLModel, table=True):
    """Modelo de base de datos para invitaciones a espacios de trabajo."""

    __tablename__ = "supplier_invitations"  # type: ignore
    # La migración `f1e2d3c4b5a6` creó esta restricción además del índice único
    # de `token`. Es redundante, pero está aplicada: el modelo la declara para no
    # proponer borrarla (PENDIENTES 3.29).
    __table_args__ = (UniqueConstraint("token", name="uq_supplier_invitation_token"),)

    id: UUID = Field(primary_key=True)
    supplier_id: UUID = Field(
        foreign_key="supplier.id", ondelete="CASCADE", index=True
    )
    email: str = Field(index=True)
    role: str = Field(default="member", sa_column_kwargs={"server_default": "member"})
    # Sin índice: la migración no lo creó y nada consulta por esta columna.
    invited_by_user_id: UUID = Field(foreign_key="users.id", ondelete="CASCADE")
    token: str = Field(unique=True, index=True)
    status: str = Field(
        default="pending", index=True, sa_column_kwargs={"server_default": "pending"}
    )
    expires_at: datetime
    created_at: datetime
    accepted_at: datetime | None = None
