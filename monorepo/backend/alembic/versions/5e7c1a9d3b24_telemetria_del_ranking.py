"""Telemetría del ranking: impresiones, interacciones, NDCG diario y prioridad en sombra.

Revision ID: 5e7c1a9d3b24
Revises: 034d29d77070
Create Date: 2026-10-03 12:00:00.000000

Plan 233, decisión 8. Compatible hacia atrás: solo crea tablas nuevas que la versión
anterior no conoce.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

revision: str = "5e7c1a9d3b24"
down_revision: str | Sequence[str] | None = "034d29d77070"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ranking_impression",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ranking_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("model_version", sqlmodel.AutoString(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["supplier_id"], ["supplier.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tender_id"], ["tender.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ranking_id", "position", name="uq_ranking_impression_ranking_position"
        ),
    )
    op.create_index(
        "ix_ranking_impression_created_at", "ranking_impression", ["created_at"]
    )
    op.create_index(
        "ix_ranking_impression_tender_created",
        "ranking_impression",
        ["tender_id", "created_at"],
    )

    op.create_table(
        "tender_interaction",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=True),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sqlmodel.AutoString(length=20), nullable=False),
        sa.Column("ranking_id", sa.Uuid(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("source", sqlmodel.AutoString(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_id"], ["supplier.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tender_id"], ["tender.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ranking_id",
            "tender_id",
            "kind",
            name="uq_tender_interaction_ranking_tender_kind",
        ),
    )
    op.create_index(
        "ix_tender_interaction_tender_created",
        "tender_interaction",
        ["tender_id", "created_at"],
    )
    op.create_index(
        "ix_tender_interaction_created_at", "tender_interaction", ["created_at"]
    )

    op.create_table(
        "ranking_metric_daily",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("model_version", sqlmodel.AutoString(length=100), nullable=False),
        sa.Column("ndcg_at_10", sa.Float(), nullable=False),
        sa.Column("ci_low", sa.Float(), nullable=False),
        sa.Column("ci_high", sa.Float(), nullable=False),
        sa.Column("rankings_evaluated", sa.Integer(), nullable=False),
        sa.Column("rankings_served", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "day", "model_version", name="uq_ranking_metric_daily_day_version"
        ),
    )

    op.create_table(
        "attachment_priority_shadow",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.Column("priority", sa.Float(), nullable=False),
        sa.Column("components", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["tender_id"], ["tender.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_attachment_priority_shadow_tender_computed",
        "attachment_priority_shadow",
        ["tender_id", "computed_at"],
    )
    op.create_index(
        "ix_attachment_priority_shadow_computed_at",
        "attachment_priority_shadow",
        ["computed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_attachment_priority_shadow_computed_at",
        table_name="attachment_priority_shadow",
    )
    op.drop_index(
        "ix_attachment_priority_shadow_tender_computed",
        table_name="attachment_priority_shadow",
    )
    op.drop_table("attachment_priority_shadow")
    op.drop_table("ranking_metric_daily")
    op.drop_index("ix_tender_interaction_created_at", table_name="tender_interaction")
    op.drop_index(
        "ix_tender_interaction_tender_created", table_name="tender_interaction"
    )
    op.drop_table("tender_interaction")
    op.drop_index(
        "ix_ranking_impression_tender_created", table_name="ranking_impression"
    )
    op.drop_index("ix_ranking_impression_created_at", table_name="ranking_impression")
    op.drop_table("ranking_impression")
