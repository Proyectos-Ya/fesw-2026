"""kanban event table

Revision ID: 18a2c3d4e5f6
Revises: 18a1b2c3d4e5
Create Date: 2026-10-27 10:05:00.000000

HU-18: historial del tablero. Cada mutación de columnas o tarjetas deja un
registro sincrónico (mismo commit de transacción que la operación). La tabla
es append-only; no hay delete por diseño.

`tender_title` queda desnormalizado para que el panel de historial no necesite
hacer join con `tender` para mostrar el título — y para que el histórico
sobreviva aunque la licitación se depure.

`event_type` queda como VARCHAR(50) sin enum Postgres a propósito: agregar un
valor al Literal del dominio no requerirá otra migración.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "18a2c3d4e5f6"
down_revision: str | Sequence[str] | None = "18a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "kanban_event",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("entity_type", sa.String(length=20), nullable=True),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("tender_id", sa.Uuid(), nullable=True),
        sa.Column("tender_title", sa.Text(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["supplier.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_kanban_event_supplier_created",
        "kanban_event",
        ["supplier_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_kanban_event_supplier_created", table_name="kanban_event")
    op.drop_table("kanban_event")
