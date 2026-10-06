"""kanban-column-color

Revision ID: b3c2d1e0f9a8
Revises: 923b0917a80b
Create Date: 2026-09-29 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

revision: str = "b3c2d1e0f9a8"
down_revision: str | Sequence[str] | None = "923b0917a80b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "kanban_column",
        sa.Column(
            "color",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="#A99A7C",
        ),
    )


def downgrade() -> None:
    op.drop_column("kanban_column", "color")
