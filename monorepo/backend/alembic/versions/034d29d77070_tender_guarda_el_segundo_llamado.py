"""tender guarda el llamado vigente y el cierre de cada llamado

Revision ID: 034d29d77070
Revises: cad6ec974305
Create Date: 2026-10-03 08:41:13.500885

Plan 233, decisión 3. Columnas nullable y sin default: compatibles hacia atrás
(la versión anterior las ignora) y sin backfill, porque el cron de estados y la
ingesta las completan cuando Mercado Público informa cada licitación.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "034d29d77070"
down_revision: str | Sequence[str] | None = "cad6ec974305"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tender", sa.Column("call_number", sa.Integer(), nullable=True))
    op.add_column(
        "tender", sa.Column("first_call_closing_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "tender", sa.Column("second_call_closing_at", sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("tender", "second_call_closing_at")
    op.drop_column("tender", "first_call_closing_at")
    op.drop_column("tender", "call_number")
