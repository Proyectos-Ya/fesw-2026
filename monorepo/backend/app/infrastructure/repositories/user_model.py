from datetime import datetime
from uuid import UUID

from sqlmodel import Field, SQLModel


class UserModel(SQLModel, table=True):
    # "users" en vez de "user" porque user es palabra reservada en PostgreSQL
    __tablename__ = "users"  # type: ignore
    id: UUID = Field(primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    full_name: str
    phone: str | None = None
    active: bool = True
    email_verified: bool = False
    created_at: datetime
    updated_at: datetime
