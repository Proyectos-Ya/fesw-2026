from datetime import datetime
from typing import ClassVar, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, TEXT
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel


class SupplierModel(SQLModel, table=True):
    id: UUID = Field(primary_key=True)
    rut: str
    legal_name: str
    trade_name: Optional[str] = None
    description: Optional[str] = None
    regions: Optional[list[str]] = None
    sectors: Optional[list[str]] = None
    certifications: Optional[list[str]] = None
    keywords: Optional[list[str]] = None
    years_experience: Optional[int] = None
    num_employees: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    profile_changed_at: Optional[datetime] = None