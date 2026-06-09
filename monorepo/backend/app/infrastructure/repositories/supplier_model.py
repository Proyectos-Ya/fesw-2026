from datetime import datetime
from typing import ClassVar, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel


class SupplierModel(SQLModel, table=True):
    __tablename__ = "supplier"   # type: ignore
    id: UUID = Field(primary_key=True)
    user_id: Optional[UUID] = Field(default=None, foreign_key="users.id", index=True, unique=True)
    rut: str
    legal_name: str
    trade_name: Optional[str] = None
    description: Optional[str] = None
    regions: Optional[list[str]] = Field(default=None, sa_column=Column(JSON))
    sectors: Optional[list[str]] = Field(default=None, sa_column=Column(JSON))
    certifications: Optional[list[str]] = Field(default=None, sa_column=Column(JSON))
    keywords: Optional[list[str]] = Field(default=None, sa_column=Column(JSON))
    years_experience: Optional[int] = None
    num_employees: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    profile_changed_at: Optional[datetime] = None