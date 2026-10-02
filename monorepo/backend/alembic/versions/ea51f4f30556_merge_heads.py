"""merge heads

Revision ID: ea51f4f30556
Revises: c3d4e5f6a7b8, d27a9c3f1b84
Create Date: 2026-09-29 19:46:26.876884

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# SQLModel mapea `str` a `sqlmodel.sql.sqltypes.AutoString`, así que las
# migraciones autogeneradas lo referencian. Sin este import fallan con
# NameError al aplicarse.
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'ea51f4f30556'
down_revision: str | Sequence[str] | None = ('c3d4e5f6a7b8', 'd27a9c3f1b84')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
