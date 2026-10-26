"""extension_instalaciones_y_trabajos

Revision ID: e3d9b1c7a842
Revises: d7a1b3c9e524
Create Date: 2026-10-04 12:00:00.000000

Plan 233, decisión 7. Tablas para registro de instalaciones de extensión
y cola de extracción distribuida con bloqueo skip locked.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e3d9b1c7a842"
down_revision: str | Sequence[str] | None = "d7a1b3c9e524"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "extension_installation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("browser", sa.String(length=32), nullable=False),
        sa.Column("browser_version", sa.String(length=64), nullable=True),
        sa.Column("extension_version", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["supplier.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_extension_installation_user_id", "extension_installation", ["user_id"])
    op.create_index("ix_extension_installation_workspace_id", "extension_installation", ["workspace_id"])
    op.create_index("ix_extension_installation_is_active", "extension_installation", ["is_active"])

    op.create_table(
        "extension_fetch_job",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("tender_code", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("leased_to_installation_id", sa.Uuid(), nullable=True),
        sa.Column("leased_at", sa.DateTime(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("result_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tender_id"], ["tender.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["leased_to_installation_id"], ["extension_installation.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_extension_fetch_job_tender_id", "extension_fetch_job", ["tender_id"])
    op.create_index("ix_extension_fetch_job_tender_code", "extension_fetch_job", ["tender_code"])
    op.create_index("ix_extension_fetch_job_status", "extension_fetch_job", ["status"])
    op.create_index("ix_extension_fetch_job_priority", "extension_fetch_job", ["priority"])
    op.create_index("ix_extension_fetch_job_lease_expires_at", "extension_fetch_job", ["lease_expires_at"])
    op.create_index(
        "ix_extension_fetch_job_queue",
        "extension_fetch_job",
        ["status", sa.text("priority DESC"), "lease_expires_at", "created_at"],
    )
    op.create_index(
        "uq_extension_fetch_job_active_tender",
        "extension_fetch_job",
        ["tender_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'leased')"),
    )


def downgrade() -> None:
    op.drop_index("uq_extension_fetch_job_active_tender", table_name="extension_fetch_job")
    op.drop_index("ix_extension_fetch_job_queue", table_name="extension_fetch_job")
    op.drop_table("extension_fetch_job")
    op.drop_table("extension_installation")
