from datetime import datetime, time
from uuid import UUID

from sqlalchemy import JSON, Column, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


class CalendarConnectionModel(SQLModel, table=True):
    __tablename__ = "calendar_connection"  # type: ignore
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_calendar_connection_user_provider"),
    )

    id: UUID = Field(primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    provider: str = Field(max_length=20)
    # Cifrados con Fernet: nunca se guardan en claro.
    access_token_encrypted: str = Field(sa_column=Column(Text, nullable=False))
    refresh_token_encrypted: str = Field(sa_column=Column(Text, nullable=False))
    expires_at: datetime
    account_email: str | None = Field(default=None, max_length=320)
    status: str = Field(max_length=20)
    created_at: datetime
    updated_at: datetime


class CalendarOAuthStateModel(SQLModel, table=True):
    __tablename__ = "calendar_oauth_state"  # type: ignore

    # Solo el SHA-256 del `state`: quien lea la tabla no puede completar un login ajeno.
    state_hash: str = Field(primary_key=True, max_length=64)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    provider: str = Field(max_length=20)
    tender_id: UUID = Field(foreign_key="tender.id")
    milestone_ids: list[str] = Field(sa_column=Column(JSON, nullable=False))
    default_time: time | None = Field(default=None)
    expires_at: datetime
    created_at: datetime


class CalendarEventLinkModel(SQLModel, table=True):
    __tablename__ = "calendar_event_link"  # type: ignore
    __table_args__ = (
        UniqueConstraint("milestone_id", "provider", name="uq_calendar_event_link_milestone_provider"),
    )

    id: UUID = Field(primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    milestone_id: UUID = Field(foreign_key="tender_milestone.id", ondelete="CASCADE")
    provider: str = Field(max_length=20)
    external_event_id: str = Field(sa_column=Column(Text, nullable=False))
    synced_due_at: datetime
    last_synced_at: datetime
