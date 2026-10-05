"""procesamiento de anexos: cola, extracciones, resumen y tope diario de Gemini

Revision ID: c5f8a2d7e413
Revises: f2c8d4a6b913
Create Date: 2026-10-04 12:00:00.000000

Plan 233, decisión 4. Compatible hacia atrás: crea cuatro tablas que la versión
anterior no conoce y agrega una columna nullable a `attachment_file`. Los únicos
parciales los compara `alembic check` por nombre y columnas, no por su WHERE: el
modelo los declara igual. `kind` ya admite `shadow_score` (decisión 9) para no
migrar de nuevo.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

revision: str = "c5f8a2d7e413"
down_revision: str | Sequence[str] | None = "f2c8d4a6b913"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TRABAJO = "attachment_processing_job"


def upgrade() -> None:
    op.add_column(
        "attachment_file",
        sa.Column(
            "status_reason", sqlmodel.AutoString(length=40), nullable=True
        ),
    )

    op.create_table(
        _TRABAJO,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sqlmodel.AutoString(length=20), nullable=False),
        sa.Column("status", sqlmodel.AutoString(length=20), nullable=False),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sqlmodel.AutoString(length=500), nullable=True),
        sa.Column("not_before", sa.DateTime(), nullable=False),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("attachment_file_id", sa.Uuid(), nullable=True),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["attachment_file_id"],
            ["attachment_file.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tender_id"], ["tender.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["supplier.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "kind IN ('extract','digest','shadow_score')",
            name="ck_attachment_processing_job_kind",
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','done','failed')",
            name="ck_attachment_processing_job_status",
        ),
        sa.CheckConstraint(
            "kind <> 'extract' OR attachment_file_id IS NOT NULL",
            name="ck_attachment_processing_job_extract_file",
        ),
        sa.CheckConstraint(
            "attempts >= 0", name="ck_attachment_processing_job_attempts"
        ),
    )
    op.create_index(
        "ix_attachment_processing_job_claim",
        _TRABAJO,
        ["status", "not_before"],
    )
    op.create_index(
        "ix_attachment_processing_job_attachment_file_id",
        _TRABAJO,
        ["attachment_file_id"],
    )
    op.create_index(
        "ix_attachment_processing_job_tender_id", _TRABAJO, ["tender_id"]
    )
    op.create_index(
        "ix_attachment_processing_job_workspace_id", _TRABAJO, ["workspace_id"]
    )
    # Idempotencia del encolado: un solo pendiente por objetivo. Solo `pending`: un
    # `digest` en curso pudo leer el conjunto viejo y no debe impedir encolar otro.
    op.create_index(
        "uq_attachment_processing_job_extract_pending",
        _TRABAJO,
        ["attachment_file_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending' AND kind = 'extract'"),
    )
    op.create_index(
        "uq_attachment_processing_job_digest_pending_shared",
        _TRABAJO,
        ["tender_id"],
        unique=True,
        postgresql_where=sa.text(
            "status = 'pending' AND kind = 'digest' AND workspace_id IS NULL"
        ),
    )
    op.create_index(
        "uq_attachment_processing_job_digest_pending_workspace",
        _TRABAJO,
        ["tender_id", "workspace_id"],
        unique=True,
        postgresql_where=sa.text(
            "status = 'pending' AND kind = 'digest' AND workspace_id IS NOT NULL"
        ),
    )

    op.create_table(
        "attachment_extraction",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("attachment_file_id", sa.Uuid(), nullable=False),
        sa.Column("tender_attachment_id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("sha256", sqlmodel.AutoString(length=64), nullable=False),
        sa.Column(
            "prompt_version", sqlmodel.AutoString(length=40), nullable=False
        ),
        sa.Column("model", sqlmodel.AutoString(length=100), nullable=False),
        sa.Column("input_mode", sqlmodel.AutoString(length=20), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("citas_total", sa.Integer(), nullable=False),
        sa.Column("citas_verificadas", sa.Integer(), nullable=False),
        sa.Column("texto_disponible", sa.Boolean(), nullable=False),
        sa.Column("usage_metadata", sa.JSON(), nullable=True),
        sa.Column("reused_from_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["attachment_file_id"],
            ["attachment_file.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tender_attachment_id"],
            ["tender_attachment.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tender_id"], ["tender.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "attachment_file_id",
            "prompt_version",
            name="uq_attachment_extraction_file_prompt",
        ),
        sa.CheckConstraint(
            "input_mode IN ('inline','files_api','text','reused')",
            name="ck_attachment_extraction_input_mode",
        ),
        sa.CheckConstraint(
            "citas_verificadas >= 0 AND citas_verificadas <= citas_total",
            name="ck_attachment_extraction_citas",
        ),
    )
    op.create_index(
        "ix_attachment_extraction_reuse",
        "attachment_extraction",
        ["tender_attachment_id", "sha256", "prompt_version"],
    )
    op.create_index(
        "ix_attachment_extraction_tender_id",
        "attachment_extraction",
        ["tender_id"],
    )

    op.create_table(
        "tender_digest",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column(
            "workspace_id", sa.Uuid(), nullable=True
        ),  # NULL = resumen compartido
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "extraction_set_hash",
            sqlmodel.AutoString(length=64),
            nullable=False,
        ),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("api_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tender_id"], ["tender.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["supplier.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("version > 0", name="ck_tender_digest_version"),
        sa.CheckConstraint(
            "source_count >= 0", name="ck_tender_digest_source_count"
        ),
    )
    op.create_index(
        "ix_tender_digest_tender_id", "tender_digest", ["tender_id"]
    )
    op.create_index(
        "ix_tender_digest_workspace_id", "tender_digest", ["workspace_id"]
    )
    op.create_index(
        "uq_tender_digest_current_shared",
        "tender_digest",
        ["tender_id"],
        unique=True,
        postgresql_where=sa.text("is_current AND workspace_id IS NULL"),
    )
    op.create_index(
        "uq_tender_digest_current_workspace",
        "tender_digest",
        ["tender_id", "workspace_id"],
        unique=True,
        postgresql_where=sa.text("is_current AND workspace_id IS NOT NULL"),
    )

    op.create_table(
        "attachment_gemini_daily_usage",
        sa.Column("day", sa.Date(), nullable=False),  # día de Chile
        sa.Column("calls", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "prompt_tokens",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "output_tokens",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("day"),
        sa.CheckConstraint(
            "calls >= 0", name="ck_attachment_gemini_daily_usage_calls"
        ),
    )


def downgrade() -> None:
    op.drop_table("attachment_gemini_daily_usage")
    for nombre in (
        "uq_tender_digest_current_workspace",
        "uq_tender_digest_current_shared",
        "ix_tender_digest_workspace_id",
        "ix_tender_digest_tender_id",
    ):
        op.drop_index(nombre, table_name="tender_digest")
    op.drop_table("tender_digest")
    op.drop_index(
        "ix_attachment_extraction_tender_id",
        table_name="attachment_extraction",
    )
    op.drop_index(
        "ix_attachment_extraction_reuse",
        table_name="attachment_extraction",
    )
    op.drop_table("attachment_extraction")
    for nombre in (
        "uq_attachment_processing_job_digest_pending_workspace",
        "uq_attachment_processing_job_digest_pending_shared",
        "uq_attachment_processing_job_extract_pending",
        "ix_attachment_processing_job_workspace_id",
        "ix_attachment_processing_job_tender_id",
        "ix_attachment_processing_job_attachment_file_id",
        "ix_attachment_processing_job_claim",
    ):
        op.drop_index(nombre, table_name=_TRABAJO)
    op.drop_table(_TRABAJO)
    op.drop_column("attachment_file", "status_reason")
