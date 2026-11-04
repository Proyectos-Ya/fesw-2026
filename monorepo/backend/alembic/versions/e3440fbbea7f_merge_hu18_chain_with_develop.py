"""merge hu18 chain with develop

Revision ID: e3440fbbea7f
Revises: 18a5f6a7b8c9, 7c1fa735a495
Create Date: 2026-11-04 14:17:26.961448

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# SQLModel mapea `str` a `sqlmodel.sql.sqltypes.AutoString`, así que las
# migraciones autogeneradas lo referencian. Sin este import fallan con
# NameError al aplicarse.
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e3440fbbea7f'
down_revision: str | Sequence[str] | None = ('18a5f6a7b8c9', '7c1fa735a495')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
