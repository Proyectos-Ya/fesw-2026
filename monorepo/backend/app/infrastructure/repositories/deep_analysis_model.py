from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlmodel import Field, SQLModel
from sqlalchemy import UniqueConstraint


class DeepAnalysisModel(SQLModel, table=True):
    __tablename__ = "deep_analysis"  # type: ignore

    id: UUID = Field(primary_key=True)
    tender_id: UUID = Field(foreign_key="tender.id", index=True)
    supplier_id: UUID = Field(foreign_key="supplier.id", index=True)
    compatibility_score: float
    recommendation: str
    justification: str
    prompt_instruction: Optional[str] = Field(default=None)
    created_at: datetime
    updated_at: datetime

    __table_args__ = (
        UniqueConstraint("tender_id", "supplier_id", name="uq_deep_analysis_tender_supplier"),
    )

