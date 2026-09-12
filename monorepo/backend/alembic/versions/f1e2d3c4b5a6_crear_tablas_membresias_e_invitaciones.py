"""crear tablas membresias e invitaciones y migrar relaciones existentes

Revision ID: f1e2d3c4b5a6
Revises: 5d0cd7e936db
Create Date: 2026-09-12 04:35:00.000000

"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa


revision: str = 'f1e2d3c4b5a6'
down_revision: str | Sequence[str] | None = '5d0cd7e936db'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Crear tabla supplier_members
    op.create_table(
        'supplier_members',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('supplier_id', sa.Uuid(), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='member'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['supplier_id'], ['supplier.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'supplier_id', name='uq_supplier_member_user_supplier'),
    )
    op.create_index(op.f('ix_supplier_members_user_id'), 'supplier_members', ['user_id'], unique=False)
    op.create_index(op.f('ix_supplier_members_supplier_id'), 'supplier_members', ['supplier_id'], unique=False)
    op.create_index(op.f('ix_supplier_members_role'), 'supplier_members', ['role'], unique=False)
    op.create_index(op.f('ix_supplier_members_status'), 'supplier_members', ['status'], unique=False)

    # 2. Crear tabla supplier_invitations
    op.create_table(
        'supplier_invitations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('supplier_id', sa.Uuid(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='member'),
        sa.Column('invited_by_user_id', sa.Uuid(), nullable=False),
        sa.Column('token', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['invited_by_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['supplier_id'], ['supplier.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token', name='uq_supplier_invitation_token'),
    )
    op.create_index(op.f('ix_supplier_invitations_supplier_id'), 'supplier_invitations', ['supplier_id'], unique=False)
    op.create_index(op.f('ix_supplier_invitations_email'), 'supplier_invitations', ['email'], unique=False)
    op.create_index(op.f('ix_supplier_invitations_token'), 'supplier_invitations', ['token'], unique=True)
    op.create_index(op.f('ix_supplier_invitations_status'), 'supplier_invitations', ['status'], unique=False)

    # 3. Poblar membresías iniciales para empresas existentes con user_id
    op.execute("""
        INSERT INTO supplier_members (id, user_id, supplier_id, role, status, created_at, updated_at)
        SELECT gen_random_uuid(), user_id, id, 'admin', 'active', created_at, updated_at
        FROM supplier
        WHERE user_id IS NOT NULL
        ON CONFLICT (user_id, supplier_id) DO NOTHING;
    """)

    # 4. Quitar restricción única en supplier.user_id si existía para permitir multi-empresa
    try:
        op.drop_constraint('supplier_user_id_key', 'supplier', type_='unique')
    except Exception:
        pass


def downgrade() -> None:
    op.drop_index(op.f('ix_supplier_invitations_status'), table_name='supplier_invitations')
    op.drop_index(op.f('ix_supplier_invitations_token'), table_name='supplier_invitations')
    op.drop_index(op.f('ix_supplier_invitations_email'), table_name='supplier_invitations')
    op.drop_index(op.f('ix_supplier_invitations_supplier_id'), table_name='supplier_invitations')
    op.drop_table('supplier_invitations')

    op.drop_index(op.f('ix_supplier_members_status'), table_name='supplier_members')
    op.drop_index(op.f('ix_supplier_members_role'), table_name='supplier_members')
    op.drop_index(op.f('ix_supplier_members_supplier_id'), table_name='supplier_members')
    op.drop_index(op.f('ix_supplier_members_user_id'), table_name='supplier_members')
    op.drop_table('supplier_members')
