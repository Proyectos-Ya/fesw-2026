"""Entidades de dominio para el matching enriquecido en sombra (Plan 233, Decisión 9)."""

from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.shared.datetime_utils import UtcDateTime, utc_now_naive

ShadowVariant = Literal["att-text-v1", "att-items-v1"]


class MatchingShadowScore(BaseModel):
    """Puntaje de matching en sombra con anexos para experimentación offline y online."""

    id: UUID = Field(default_factory=uuid4)
    ranking_id: UUID | None = None
    supplier_id: UUID
    tender_id: UUID
    variant: ShadowVariant = "att-text-v1"
    baseline_score: float
    shadow_score: float
    reranker_score: float | None = None
    best_match: float | None = None
    coverage: float | None = None
    model_version: str
    calculated_at: UtcDateTime = Field(default_factory=utc_now_naive)


class TenderAttachmentItem(BaseModel):
    """Pseudo-partida extraída de anexos oficiales para matching en sombra.

    Viven completamente aisladas de `tender_items` para no contaminar las consultas
    de producción.
    """

    id: UUID = Field(default_factory=uuid4)
    tender_id: UUID
    title: str
    description: str | None = None
    quantity: float | None = None
    unit: str | None = None
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)
