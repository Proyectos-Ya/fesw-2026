from datetime import datetime
from uuid import UUID

from sqlalchemy import Column, Index, Text
from sqlmodel import Field, SQLModel


class TenderMilestoneModel(SQLModel, table=True):
    __tablename__ = "tender_milestone"  # type: ignore
    __table_args__ = (
        Index("ix_tender_milestone_user_tender", "user_id", "tender_id"),
        # El loop de recordatorios barre por estas dos columnas cada hora.
        Index("ix_tender_milestone_recordatorio", "reminder_days_before", "reminder_sent_at"),
    )

    id: UUID = Field(primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    tender_id: UUID = Field(foreign_key="tender.id", index=True)
    kind: str = Field(max_length=40)
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, sa_column=Column(Text))
    source: str = Field(max_length=40)
    source_document_id: UUID | None = Field(default=None)
    source_file_id: UUID | None = Field(default=None, index=True)
    source_excerpt: str | None = Field(default=None, max_length=1000)
    due_at: datetime
    has_time: bool
    # Recordatorio del hito (HU-16, criterio 10). Nulo = el usuario no lo activó.
    reminder_days_before: int | None = Field(default=None)
    reminder_sent_at: datetime | None = Field(default=None)
    created_at: datetime
    updated_at: datetime
