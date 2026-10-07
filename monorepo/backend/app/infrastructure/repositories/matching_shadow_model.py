"""Modelos de base de datos para el matching en sombra (Plan 233, Decisión 9)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class MatchingShadowScoreModel(SQLModel, table=True):
    """Modelo de base de datos para la tabla 'matching_shadow_score' en PostgreSQL."""

    __tablename__ = "matching_shadow_score"  # type: ignore

    __table_args__ = (
        UniqueConstraint(
            "supplier_id",
            "tender_id",
            "variant",
            name="uq_matching_shadow_supplier_tender_variant",
        ),
    )

    id: UUID = Field(primary_key=True)
    ranking_id: UUID | None = Field(default=None, index=True)
    supplier_id: UUID = Field(foreign_key="supplier.id", index=True)
    tender_id: UUID = Field(foreign_key="tender.id", index=True)
    variant: str = Field(index=True)
    baseline_score: float
    shadow_score: float
    reranker_score: float | None = Field(default=None)
    best_match: float | None = Field(default=None)
    coverage: float | None = Field(default=None)
    model_version: str
    calculated_at: datetime


class TenderAttachmentItemModel(SQLModel, table=True):
    """Pseudo-partidas extraídas de anexos oficiales para matching en sombra.

    Viven en 'tender_attachment_item' separadas de 'tender_items'.
    """

    __tablename__ = "tender_attachment_item"  # type: ignore

    id: UUID = Field(primary_key=True)
    tender_id: UUID = Field(foreign_key="tender.id", index=True)
    title: str
    description: str | None = Field(default=None)
    quantity: float | None = Field(default=None)
    unit: str | None = Field(default=None)
    created_at: datetime
