"""archivos de anexos y cupo mensual de subidas

Revision ID: e4a7c2d9b815
Revises: 5e7c1a9d3b24
Create Date: 2026-10-03 15:00:00.000000

Plan 233, decisión 2. Compatible hacia atrás: solo crea dos tablas que la versión
anterior no conoce. `visibility` y `trust` nacen con su default para que la
decisión 6 no necesite otra migración, y el CHECK de `source` ya admite
`extension` (decisión 7) y `legacy_chat` (migración del chat). Texto con CHECK y
no ENUM nativo: un valor agregado a un ENUM de Postgres no se revierte en el
downgrade, y un CHECK se reemplaza.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

revision: str = "e4a7c2d9b815"
down_revision: str | Sequence[str] | None = "5e7c1a9d3b24"  # = salida de `alembic heads`
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attachment_file",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tender_attachment_id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("sha256", sqlmodel.AutoString(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mime_declared", sqlmodel.AutoString(length=255), nullable=True),
        sa.Column("storage_key", sqlmodel.AutoString(length=512), nullable=False),
        sa.Column("source", sqlmodel.AutoString(length=20), nullable=False),
        sa.Column("uploader_user_id", sa.Uuid(), nullable=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column(
            "visibility",
            sqlmodel.AutoString(length=20),
            server_default="private",
            nullable=False,
        ),
        sa.Column(
            "trust",
            sqlmodel.AutoString(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("status", sqlmodel.AutoString(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("purge_after", sa.DateTime(), nullable=True),
        # CASCADE como `tender_attachment`: el archivo cuelga de la licitación y de la empresa.
        sa.ForeignKeyConstraint(
            ["tender_attachment_id"], ["tender_attachment.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tender_id"], ["tender.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["supplier.id"], ondelete="CASCADE"),
        # SET NULL: el archivo es de la empresa; borrar la cuenta no lo borra.
        sa.ForeignKeyConstraint(["uploader_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tender_attachment_id",
            "sha256",
            "workspace_id",
            name="uq_attachment_file_attachment_sha_workspace",
        ),
        sa.CheckConstraint(
            "status IN ('uploading','stored','unsupported','rejected','purged')",
            name="ck_attachment_file_status",
        ),
        sa.CheckConstraint(
            "visibility IN ('private','shared')", name="ck_attachment_file_visibility"
        ),
        sa.CheckConstraint(
            "trust IN ('pending','corroborated','conflict','rejected')",
            name="ck_attachment_file_trust",
        ),
        sa.CheckConstraint(
            "source IN ('manual','extension','legacy_chat')",
            name="ck_attachment_file_source",
        ),
        sa.CheckConstraint("size_bytes > 0", name="ck_attachment_file_size"),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_attachment_file_sha256"),
    )
    # La UQ empieza por tender_attachment_id y ya cubre esa FK; (workspace_id, sha256)
    # cubre la FK de empresa y la deduplicación por objeto.
    op.create_index("ix_attachment_file_tender_id", "attachment_file", ["tender_id"])
    op.create_index(
        "ix_attachment_file_workspace_sha", "attachment_file", ["workspace_id", "sha256"]
    )
    op.create_index(
        "ix_attachment_file_uploader_user_id", "attachment_file", ["uploader_user_id"]
    )

    op.create_table(
        "attachment_upload_quota",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("used", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["supplier.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("workspace_id", "month"),
        sa.CheckConstraint("used >= 0", name="ck_attachment_upload_quota_used"),
    )


def downgrade() -> None:
    op.drop_table("attachment_upload_quota")
    op.drop_index("ix_attachment_file_uploader_user_id", table_name="attachment_file")
    op.drop_index("ix_attachment_file_workspace_sha", table_name="attachment_file")
    op.drop_index("ix_attachment_file_tender_id", table_name="attachment_file")
    op.drop_table("attachment_file")
