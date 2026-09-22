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
    # Las marcas de tiempo que tenían la licitación y el proveedor cuando se
    # escribió este análisis. Se guardan para saber si algo cambió después
    # comparando por igualdad y no por orden: comparar fechas de dos relojes
    # distintos convierte cualquier desfase —un volcado restaurado, un reloj
    # adelantado— en un "desactualizado" permanente que el usuario no puede
    # quitar, porque regenerar vuelve a escribir una fecha anterior.
    tender_updated_at: UtcDateTime | None = None
    supplier_updated_at: UtcDateTime | None = None
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)
    updated_at: UtcDateTime = Field(default_factory=utc_now_naive)

    @field_validator("compatibility_score")
    @classmethod
    def validate_compatibility_score(cls, value: float) -> float:
        if not (0.0 <= value <= 100.0):
            raise ValueError("compatibility_score must be between 0.0 and 100.0")
        return value
