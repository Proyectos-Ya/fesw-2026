from datetime import datetime
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class DeepAnalysisModel(SQLModel, table=True):
    __tablename__ = "deep_analysis"  # type: ignore

    id: UUID = Field(primary_key=True)
    tender_id: UUID = Field(foreign_key="tender.id", index=True)
    supplier_id: UUID = Field(foreign_key="supplier.id", index=True)
    compatibility_score: float
    recommendation: str
    justification: str
    prompt_instruction: str | None = Field(default=None)
    # Estado de la licitación y del proveedor en el momento de generar. Nulos
    # en los análisis anteriores a esta columna.
    tender_updated_at: datetime | None = Field(default=None)
    supplier_updated_at: datetime | None = Field(default=None)
    created_at: datetime
    updated_at: datetime

    __table_args__ = (
        UniqueConstraint(
            "tender_id", "supplier_id", name="uq_deep_analysis_tender_supplier"
        ),
    )
