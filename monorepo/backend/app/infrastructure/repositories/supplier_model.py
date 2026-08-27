from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class SupplierModel(SQLModel, table=True):
    __tablename__ = "supplier"  # type: ignore
    id: UUID = Field(primary_key=True)
    user_id: UUID | None = Field(
        default=None, foreign_key="users.id", index=True, unique=True
    )
    rut: str
    legal_name: str
    trade_name: str | None = None
    description: str | None = None
    regions: list[str] | None = Field(default=None, sa_column=Column(JSON))
    sectors: list[str] | None = Field(default=None, sa_column=Column(JSON))
    certifications: list[str] | None = Field(default=None, sa_column=Column(JSON))
    keywords: list[str] | None = Field(default=None, sa_column=Column(JSON))
    years_experience: int | None = None
    num_employees: int | None = None
    created_at: datetime
    updated_at: datetime
    profile_changed_at: datetime | None = None
