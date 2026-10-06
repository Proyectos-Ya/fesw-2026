"""historial del cron de estados

Revision ID: 923b0917a80b
Revises: e19b7f3a2c04
Create Date: 2026-10-06 12:00:00.000000

Solo agrega una tabla: compatible con la versión anterior durante el despliegue.
La versión vieja del cron no la lee ni la escribe.

RLS: en producción lo activa el event trigger `ensure_rls` del panel de
Supabase al crear cada tabla, no esta migración.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "923b0917a80b"
down_revision: str | Sequence[str] | None = "e19b7f3a2c04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sync_estados_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("complete", sa.Boolean(), nullable=False),
        sa.Column("listed", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sync_estados_run_started_at",
        "sync_estados_run",
        ["started_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_sync_estados_run_started_at", table_name="sync_estados_run")
    op.drop_table("sync_estados_run")
