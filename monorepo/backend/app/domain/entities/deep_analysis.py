from typing import Literal, get_args
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from app.shared.datetime_utils import UtcDateTime, utc_now_naive

RecommendationLiteral = Literal["Postular", "Evaluar con cautela", "No recomendado"]

# Derivada del propio Literal: al ser una tupla de literales, los type checkers
# pueden estrechar `str` a RecommendationLiteral tras un chequeo de pertenencia.
VALID_RECOMMENDATIONS: tuple[RecommendationLiteral, ...] = get_args(
    RecommendationLiteral
)


class DeepAnalysis(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    tender_id: UUID
    supplier_id: UUID
    compatibility_score: float
    recommendation: RecommendationLiteral
    justification: str
    prompt_instruction: str | None = None
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)
    updated_at: UtcDateTime = Field(default_factory=utc_now_naive)

    @field_validator("compatibility_score")
    @classmethod
    def validate_compatibility_score(cls, value: float) -> float:
        if not (0.0 <= value <= 100.0):
            raise ValueError("compatibility_score must be between 0.0 and 100.0")
        return value
