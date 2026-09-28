"""agrega last_access_at en supplier_members para HU-13

Revision ID: c3d4e5f6a7b8
Revises: f1e2d3c4b5a6
Create Date: 2026-09-28 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "f1e2d3c4b5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "supplier_members",
        sa.Column("last_access_at", sa.DateTime(), nullable=True),
    )
    op.execute(
        "UPDATE supplier_members SET last_access_at = updated_at WHERE last_access_at IS NULL;"
    )


def downgrade() -> None:
    op.drop_column("supplier_members", "last_access_at")
