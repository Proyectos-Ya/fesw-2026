"""merge: kanban y postulacion

Revision ID: 9fc5e8be46b9
Revises: c7f1d4a9e302, d4e8a1b2c3f5
Create Date: 2026-10-07 23:57:42.891985

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# SQLModel mapea `str` a `sqlmodel.sql.sqltypes.AutoString`, así que las
# migraciones autogeneradas lo referencian. Sin este import fallan con
# NameError al aplicarse.
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '9fc5e8be46b9'
down_revision: str | Sequence[str] | None = ('c7f1d4a9e302', 'd4e8a1b2c3f5')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
