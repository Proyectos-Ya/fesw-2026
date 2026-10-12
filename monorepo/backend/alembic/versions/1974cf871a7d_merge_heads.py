"""merge heads

Une las dos cabezas que quedaron en develop al mergear por separado el banco de
capacidades (HU-20, `eead2dba418a`, #274) y el tablero kanban (`fa511ba1ba22`,
#249). Cada PR tenía una sola cabeza contra el develop de su momento, pero el
kanban cuelga de `f1e2d3c4b5a6`: juntos, `alembic upgrade head` aborta.

Las dos ya están en develop, así que no se repunta ninguna (AGENTS.md §3): se
unen acá. No cambia el esquema.

Revision ID: 1974cf871a7d
Revises: eead2dba418a, fa511ba1ba22
Create Date: 2026-09-30 17:02:08.672130

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# SQLModel mapea `str` a `sqlmodel.sql.sqltypes.AutoString`, así que las
# migraciones autogeneradas lo referencian. Sin este import fallan con
# NameError al aplicarse.
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '1974cf871a7d'
down_revision: str | Sequence[str] | None = ('eead2dba418a', 'fa511ba1ba22')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
