"""merge tender chat and notifications heads

Revision ID: 17a3c4130f5a
Revises: 869745767a10, 9a1c4f7b2e08
Create Date: 2026-08-28 03:44:24.738450

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# SQLModel mapea `str` a `sqlmodel.sql.sqltypes.AutoString`, así que las
# migraciones autogeneradas lo referencian. Sin este import fallan con
# NameError al aplicarse.
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '17a3c4130f5a'
down_revision: str | Sequence[str] | None = ('869745767a10', '9a1c4f7b2e08')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
