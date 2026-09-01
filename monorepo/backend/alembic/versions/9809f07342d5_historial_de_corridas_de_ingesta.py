"""historial de corridas de ingesta

La ingesta pedía siempre "las últimas 24 h contadas desde ahora", sin guardar
hasta dónde llegó la corrida anterior. Con el scheduler dentro del proceso web
casi nunca fallaba, porque el proceso está siempre vivo. Con un cron diario sí:
una ejecución que no corre —el servicio caído, un despliegue fallido, la cuota
agotada— deja un hueco de horas o días que nadie vuelve a mirar.

`window_to` de la última corrida con estado `ok` es el cursor. La tabla es nueva,
así que es compatible hacia atrás por construcción: la versión anterior del
código convive con ella sin enterarse, como exige el `preDeployCommand` de
`railway.toml`.

Revision ID: 9809f07342d5
Revises: 0af9129cc120
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9809f07342d5"
down_revision: str | Sequence[str] | None = "0af9129cc120"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "ingestion_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("window_from", sa.DateTime(), nullable=False),
        sa.Column("window_to", sa.DateTime(), nullable=False),
        sa.Column("listed", sa.Integer(), nullable=False),
        sa.Column("processed", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # El cursor se lee como MAX(window_to) WHERE status = 'ok', así que el
    # índice cubre las dos columnas de esa consulta.
    op.create_index(
        "ix_ingestion_run_cursor", "ingestion_run", ["status", "window_to"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_ingestion_run_cursor", table_name="ingestion_run")
    op.drop_table("ingestion_run")
