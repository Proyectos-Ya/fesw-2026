"""matching_en_sombra

Revision ID: b4c9e1d8a735
Revises: e3d9b1c7a842
Create Date: 2026-10-05 04:00:00.000000

Plan 233, decisión 9. Tablas para matching en sombra con anexos:
`matching_shadow_score` y `tender_attachment_item`.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4c9e1d8a735"
down_revision: str | Sequence[str] | None = "e3d9b1c7a842"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Tabla matching_shadow_score
    op.create_table(
        "matching_shadow_score",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ranking_id", sa.Uuid(), nullable=True),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("variant", sa.String(length=64), nullable=False),
        sa.Column("baseline_score", sa.Float(), nullable=False),
        sa.Column("shadow_score", sa.Float(), nullable=False),
        sa.Column("reranker_score", sa.Float(), nullable=True),
        sa.Column("best_match", sa.Float(), nullable=True),
        sa.Column("coverage", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("calculated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["supplier.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tender_id"],
            ["tender.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "supplier_id",
            "tender_id",
            "variant",
            name="uq_matching_shadow_supplier_tender_variant",
        ),
    )
    op.create_index(
        "ix_matching_shadow_score_ranking_id",
        "matching_shadow_score",
        ["ranking_id"],
        unique=False,
    )
    op.create_index(
        "ix_matching_shadow_score_supplier_id",
        "matching_shadow_score",
        ["supplier_id"],
        unique=False,
    )
    op.create_index(
        "ix_matching_shadow_score_tender_id",
        "matching_shadow_score",
        ["tender_id"],
        unique=False,
    )
    op.create_index(
        "ix_matching_shadow_score_variant",
        "matching_shadow_score",
        ["variant"],
        unique=False,
    )

    # 2. Tabla tender_attachment_item
    op.create_table(
        "tender_attachment_item",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tender_id"],
            ["tender.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tender_attachment_item_tender_id",
        "tender_attachment_item",
        ["tender_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tender_attachment_item_tender_id",
        table_name="tender_attachment_item",
    )
    op.drop_table("tender_attachment_item")

    op.drop_index(
        "ix_matching_shadow_score_variant",
        table_name="matching_shadow_score",
    )
    op.drop_index(
        "ix_matching_shadow_score_tender_id",
        table_name="matching_shadow_score",
    )
    op.drop_index(
        "ix_matching_shadow_score_supplier_id",
        table_name="matching_shadow_score",
    )
    op.drop_index(
        "ix_matching_shadow_score_ranking_id",
        table_name="matching_shadow_score",
    )
    op.drop_table("matching_shadow_score")
