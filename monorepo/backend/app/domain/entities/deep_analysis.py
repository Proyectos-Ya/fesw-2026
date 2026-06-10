from datetime import datetime, timezone
from typing import Optional, Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator


class DeepAnalysis(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    tender_id: UUID
    supplier_id: UUID
    compatibility_score: float
    recommendation: Literal["Postular", "Evaluar con cautela", "No recomendado"]
    justification: str
    prompt_instruction: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    @field_validator("compatibility_score")
    @classmethod
    def validate_compatibility_score(cls, value: float) -> float:
        if not (0.0 <= value <= 100.0):
            raise ValueError("compatibility_score must be between 0.0 and 100.0")
        return value
