from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.shared.datetime_utils import utc_now_naive


class QuestionModel(SQLModel, table=True):
    # Infraestructura del modelo de question adaptada.
    __tablename__ = "profile_question"  # type: ignore

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    provider_id: UUID = Field(index=True, nullable=False)
    # tender_id: Optional[UUID] = Field(default=None, nullable=True) # Por el pmv, lo dejamos comentado

    discrepancy_type: str | None = Field(default="Category", nullable=True)
    tender_requirement: str | None = Field(default=None, nullable=True)
    question: str = Field(nullable=False)
    target_profile_field: str = Field(nullable=False)
    answered: bool = Field(default=False, index=True)
    answer: str | None = Field(default=None, nullable=True)
    omitted: bool = Field(default=False, index=True)

    generated_at: datetime = Field(default_factory=utc_now_naive, nullable=False)
    answered_at: datetime | None = Field(default=None, nullable=True)

    # Campos para el arbol del pmv
    target_category: str = Field(index=True, default="general")
    options: list[str] = Field(sa_column=Column(JSONB, nullable=False, default=[]))
