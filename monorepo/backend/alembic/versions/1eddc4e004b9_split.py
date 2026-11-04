"""split monolithic onboarding tour into independent home detail and draft flags

Revision ID: 1eddc4e004b9
Revises: a9810a282f7a
Create Date: 2026-11-03 17:40:23.682357

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '1eddc4e004b9'
down_revision: str | Sequence[str] | None = 'a9810a282f7a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('tour_home_completed', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('users', sa.Column('tour_detail_completed', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('users', sa.Column('tour_draft_completed', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.drop_column('users', 'has_completed_onboarding')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('users', sa.Column('has_completed_onboarding', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False))
    op.drop_column('users', 'tour_draft_completed')
    op.drop_column('users', 'tour_detail_completed')
    op.drop_column('users', 'tour_home_completed')
