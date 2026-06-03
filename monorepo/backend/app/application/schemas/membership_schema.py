from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.entities.membership import MembershipRole, MembershipStatus
from app.domain.entities.supplier import Supplier


class JoinSupplierSchema(BaseModel):
    """Solicitud de unión a una empresa identificada por su RUT."""

    rut: str = Field(max_length=12)


class MembershipPublicSchema(BaseModel):
    id: UUID
    user_id: UUID
    supplier_id: UUID
    role: MembershipRole
    status: MembershipStatus
    joined_at: Optional[datetime] = None
    created_at: datetime


class SupplierCreatedSchema(BaseModel):
    """Respuesta al crear una empresa: el proveedor y la membresía admin."""

    supplier: Supplier
    membership: MembershipPublicSchema
