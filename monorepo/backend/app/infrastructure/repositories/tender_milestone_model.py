from datetime import datetime
from uuid import UUID

from sqlalchemy import Column, Index, Text
from sqlmodel import Field, SQLModel


class TenderMilestoneModel(SQLModel, table=True):
    __tablename__ = "tender_milestone"  # type: ignore
    __table_args__ = (
        Index("ix_tender_milestone_user_tender", "user_id", "tender_id"),
    )

    id: UUID = Field(primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    tender_id: UUID = Field(foreign_key="tender.id", index=True)
    kind: str = Field(max_length=40)
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, sa_column=Column(Text))
    source: str = Field(max_length=40)
    source_document_id: UUID | None = Field(default=None)
    source_excerpt: str | None = Field(default=None, max_length=1000)
    due_at: datetime
    has_time: bool
    created_at: datetime
    updated_at: datetime
