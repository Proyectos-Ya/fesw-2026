"""create tender chat tables

Revision ID: e1b10ad7ddaf
Revises: 82786321a8db
Create Date: 2026-08-27 23:17:00.634858

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# SQLModel mapea `str` a `sqlmodel.sql.sqltypes.AutoString`, así que las
# migraciones autogeneradas lo referencian. Sin este import fallan con
# NameError al aplicarse.
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e1b10ad7ddaf'
down_revision: str | Sequence[str] | None = '82786321a8db'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('tender_chat_sessions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('tender_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('title', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['tender_id'], ['tender.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tender_chat_sessions_is_active'), 'tender_chat_sessions', ['is_active'], unique=False)
    op.create_index(op.f('ix_tender_chat_sessions_tender_id'), 'tender_chat_sessions', ['tender_id'], unique=False)
    op.create_index(op.f('ix_tender_chat_sessions_user_id'), 'tender_chat_sessions', ['user_id'], unique=False)
    op.add_column('tender_chat_messages', sa.Column('session_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_tender_chat_messages_session_id'), 'tender_chat_messages', ['session_id'], unique=False)
    op.create_foreign_key(None, 'tender_chat_messages', 'tender_chat_sessions', ['session_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(None, 'tender_chat_messages', type_='foreignkey')
    op.drop_index(op.f('ix_tender_chat_messages_session_id'), table_name='tender_chat_messages')
    op.drop_column('tender_chat_messages', 'session_id')
    op.drop_index(op.f('ix_tender_chat_sessions_user_id'), table_name='tender_chat_sessions')
    op.drop_index(op.f('ix_tender_chat_sessions_tender_id'), table_name='tender_chat_sessions')
    op.drop_index(op.f('ix_tender_chat_sessions_is_active'), table_name='tender_chat_sessions')
    op.drop_table('tender_chat_sessions')

