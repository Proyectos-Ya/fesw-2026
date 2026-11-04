"""supplier match threshold

Revision ID: 18a5f6a7b8c9
Revises: 18a4e5f6a7b8
Create Date: 2026-10-27 10:20:00.000000

HU-18: umbral de match a nivel de workspace. Si está seteado, el scanner
usa este valor para todos los miembros; si no, cae al `threshold` individual
de cada `NotificationPreference`. Rango (0, 1] en la misma escala que
`MatchingResult.final_score`.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "18a5f6a7b8c9"
down_revision: str | Sequence[str] | None = "18a4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "supplier", sa.Column("match_threshold", sa.Float(), nullable=True)
    )
    op.create_check_constraint(
        "ck_supplier_match_threshold_range",
        "supplier",
        "match_threshold IS NULL OR (match_threshold > 0 AND match_threshold <= 1)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_supplier_match_threshold_range", "supplier", type_="check"
    )
    op.drop_column("supplier", "match_threshold")
