from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlmodel import Field, SQLModel


class MembershipModel(SQLModel, table=True):
    # Relación usuario ↔ proveedor (empresa)
    __tablename__ = "supplier_user"  # type: ignore
    id: UUID = Field(primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    supplier_id: UUID = Field(foreign_key="supplier.id", index=True)
    role: str
    status: str
    joined_at: Optional[datetime] = None
    created_at: datetime
