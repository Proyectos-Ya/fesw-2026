from typing import List, Optional
from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

class QuestionModel(SQLModel, table=True):
    # Infraestructura del modelo de question adaptada.
    __tablename__ = "profile_question" # type: ignore
    
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    provider_id: UUID = Field(index=True, nullable=False)
    # tender_id: Optional[UUID] = Field(default=None, nullable=True) # Por el pmv, lo dejamos comentado

    discrepancy_tipe: Optional[str] = Field(default="Category", nullable=True)
    tender_requirement: Optional[str] = Field(default=None, nullable=True)
    question: str = Field(nullable=False)
    target_profile_field: str = Field(nullable=False)
    answered: bool = Field(default=False, index=True)
    answer: Optional[str] = Field(default=None, nullable=True)
    omitted: bool = Field(default=False, index=True)

    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    answered_at: Optional[datetime] = Field(default=None, nullable=True)

    # Campos para el arbol del pmv
    target_category: str = Field(index=True, default="general")
    options: List[str] = Field(sa_column=Column(JSONB, nullable=False, default=[]))