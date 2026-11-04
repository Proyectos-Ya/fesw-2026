"""Tablas de la telemetría del ranking (plan 233, decisión 8).

Sin `index=True`: todos los índices van en `__table_args__` con el nombre exacto
que crea la migración, para que `alembic check` no proponga renombrarlos.

Retención: `ranking_impression`, `tender_interaction` y `attachment_priority_shadow`
se purgan a los 90 días; `ranking_metric_daily` es un agregado sin datos
personales y se conserva. Las FK a `users`, `supplier` y `tender` llevan
`ondelete="CASCADE"`, así que borrar una cuenta o una licitación limpia la
telemetría sola.
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Column, Index, UniqueConstraint
from sqlmodel import Field, SQLModel


class RankingImpressionModel(SQLModel, table=True):
    """Una posición servida por `/tenders/recommended`, en el orden del modelo."""

    __tablename__ = "ranking_impression"  # type: ignore
    __table_args__ = (
        UniqueConstraint(
            "ranking_id", "position", name="uq_ranking_impression_ranking_position"
        ),
        # Día del NDCG y purga.
        Index("ix_ranking_impression_created_at", "created_at"),
        Index("ix_ranking_impression_tender_created", "tender_id", "created_at"),
    )

    id: UUID = Field(primary_key=True)
    ranking_id: UUID
    supplier_id: UUID = Field(foreign_key="supplier.id", ondelete="CASCADE")
    user_id: UUID = Field(foreign_key="users.id", ondelete="CASCADE")
    tender_id: UUID = Field(foreign_key="tender.id", ondelete="CASCADE")
    position: int
    score: float | None = Field(default=None)
    model_version: str = Field(max_length=100)
    created_at: datetime


class TenderInteractionModel(SQLModel, table=True):
    """Algo que el usuario hizo con una licitación; `ranking_id` solo si se atribuyó."""

    __tablename__ = "tender_interaction"  # type: ignore
    __table_args__ = (
        # Idempotencia: una vez por lista, licitación y tipo. Con ranking_id NULL
        # Postgres no compara (NULLS DISTINCT), así que lo no atribuido no se
        # deduplica, a propósito.
        UniqueConstraint(
            "ranking_id",
            "tender_id",
            "kind",
            name="uq_tender_interaction_ranking_tender_kind",
        ),
        Index("ix_tender_interaction_tender_created", "tender_id", "created_at"),
        Index("ix_tender_interaction_created_at", "created_at"),
    )

    id: UUID = Field(primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", ondelete="CASCADE")
    supplier_id: UUID | None = Field(
        default=None, foreign_key="supplier.id", ondelete="CASCADE"
    )
    tender_id: UUID = Field(foreign_key="tender.id", ondelete="CASCADE")
    kind: str = Field(max_length=20)
    ranking_id: UUID | None = Field(default=None)
    position: int | None = Field(default=None)
    source: str = Field(max_length=20)
    created_at: datetime


class RankingMetricDailyModel(SQLModel, table=True):
    """NDCG@10 de un día de Chile por versión del modelo. Agregado: no se purga."""

    __tablename__ = "ranking_metric_daily"  # type: ignore
    __table_args__ = (
        UniqueConstraint(
            "day", "model_version", name="uq_ranking_metric_daily_day_version"
        ),
    )

    id: UUID = Field(primary_key=True)
    day: date
    model_version: str = Field(max_length=100)
    ndcg_at_10: float
    ci_low: float
    ci_high: float
    rankings_evaluated: int
    rankings_served: int
    computed_at: datetime


class AttachmentPriorityShadowModel(SQLModel, table=True):
    """Foto de la prioridad de anexos en sombra. Nadie la consume todavía."""

    __tablename__ = "attachment_priority_shadow"  # type: ignore
    __table_args__ = (
        Index(
            "ix_attachment_priority_shadow_tender_computed", "tender_id", "computed_at"
        ),
        Index("ix_attachment_priority_shadow_computed_at", "computed_at"),
    )

    id: UUID = Field(primary_key=True)
    tender_id: UUID = Field(foreign_key="tender.id", ondelete="CASCADE")
    computed_at: datetime
    priority: float
    components: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
