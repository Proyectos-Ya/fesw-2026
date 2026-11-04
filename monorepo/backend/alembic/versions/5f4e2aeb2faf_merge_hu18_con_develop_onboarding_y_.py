"""merge hu18 con develop onboarding y split

Revision ID: 5f4e2aeb2faf
Revises: 1eddc4e004b9, 6eeed6fc708e
Create Date: 2026-11-04 20:35:47.839272

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# SQLModel mapea `str` a `sqlmodel.sql.sqltypes.AutoString`, así que las
# migraciones autogeneradas lo referencian. Sin este import fallan con
# NameError al aplicarse.
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '5f4e2aeb2faf'
down_revision: str | Sequence[str] | None = ('1eddc4e004b9', '6eeed6fc708e')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
