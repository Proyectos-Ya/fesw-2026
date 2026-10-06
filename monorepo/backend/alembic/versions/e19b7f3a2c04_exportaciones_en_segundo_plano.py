"""exportaciones en segundo plano (HdU 19)

Revision ID: e19b7f3a2c04
Revises: e19a4c2b7d01
Create Date: 2026-09-28 14:00:00.000000

Solo agrega una tabla: compatible con la versión anterior de la API durante el
despliegue.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e19b7f3a2c04"
down_revision: str | Sequence[str] | None = "e19a4c2b7d01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "export_job",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("format", sa.String(length=8), nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        # El archivo generado; se vacía al vencer a los 7 días.
        sa.Column("content", sa.LargeBinary(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_id"], ["supplier.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tender_id"], ["tender.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_export_job_user_id"), "export_job", ["user_id"], unique=False)
    op.create_index(op.f("ix_export_job_status"), "export_job", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_export_job_status"), table_name="export_job")
    op.drop_index(op.f("ix_export_job_user_id"), table_name="export_job")
    op.drop_table("export_job")
