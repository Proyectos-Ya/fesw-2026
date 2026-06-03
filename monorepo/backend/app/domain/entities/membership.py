from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MembershipRole(str, Enum):
    """Rol de un usuario dentro de una empresa (proveedor)."""

    ADMIN = "admin"
    MEMBER = "member"
    # NOTA: el rol OWNER (no expulsable por admins) se agregará en una fase posterior.


class MembershipStatus(str, Enum):
    """Estado de la membresía: solicitud pendiente o miembro activo."""

    PENDING = "pending"
    ACTIVE = "active"


class SupplierMembership(BaseModel):
    """Relación usuario ↔ empresa (tabla proveedor_usuario en el diseño)."""

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    supplier_id: UUID
    role: MembershipRole = MembershipRole.MEMBER
    status: MembershipStatus = MembershipStatus.PENDING
    # Se setea al aprobar la solicitud (pasa a ACTIVE)
    joined_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
