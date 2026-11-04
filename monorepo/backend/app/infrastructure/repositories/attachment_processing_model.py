"""Modelos SQL para el procesamiento de anexos, extracciones, resumen y uso diario de Gemini (plan 233, decisión 4).

Sin `index=True`: los índices van en `__table_args__` con el nombre exacto de la migración.
Server defaults declarados para compare_server_default de Alembic.
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Column,
    Index,
    UniqueConstraint,
    text,
)
from sqlmodel import Field, SQLModel


class AttachmentProcessingJobModel(SQLModel, table=True):
    __tablename__ = "attachment_processing_job"  # type: ignore
    __table_args__ = (
        CheckConstraint(
            "kind IN ('extract','digest','shadow_score')",
            name="ck_attachment_processing_job_kind",
        ),
        CheckConstraint(
            "status IN ('pending','running','done','failed')",
            name="ck_attachment_processing_job_status",
        ),
        CheckConstraint(
            "kind <> 'extract' OR attachment_file_id IS NOT NULL",
            name="ck_attachment_processing_job_extract_file",
        ),
        CheckConstraint(
            "attempts >= 0", name="ck_attachment_processing_job_attempts"
        ),
        Index("ix_attachment_processing_job_claim", "status", "not_before"),
        Index(
            "ix_attachment_processing_job_attachment_file_id",
            "attachment_file_id",
        ),
        Index("ix_attachment_processing_job_tender_id", "tender_id"),
        Index("ix_attachment_processing_job_workspace_id", "workspace_id"),
        Index(
            "uq_attachment_processing_job_extract_pending",
            "attachment_file_id",
            unique=True,
            postgresql_where=text("status = 'pending' AND kind = 'extract'"),
        ),
        Index(
            "uq_attachment_processing_job_digest_pending_shared",
            "tender_id",
            unique=True,
            postgresql_where=text(
                "status = 'pending' AND kind = 'digest' AND workspace_id IS NULL"
            ),
        ),
        Index(
            "uq_attachment_processing_job_digest_pending_workspace",
            "tender_id",
            "workspace_id",
            unique=True,
            postgresql_where=text(
                "status = 'pending' AND kind = 'digest' AND workspace_id IS NOT NULL"
            ),
        ),
    )

    id: UUID = Field(primary_key=True)
    kind: str = Field(max_length=20)
    status: str = Field(max_length=20)
    priority: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    attempts: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    last_error: str | None = Field(default=None, max_length=500)
    not_before: datetime
    locked_at: datetime | None = Field(default=None)
    attachment_file_id: UUID | None = Field(
        default=None, foreign_key="attachment_file.id", ondelete="CASCADE"
    )
    tender_id: UUID = Field(foreign_key="tender.id", ondelete="CASCADE")
    workspace_id: UUID | None = Field(
        default=None, foreign_key="supplier.id", ondelete="CASCADE"
    )
    created_at: datetime
    updated_at: datetime


class AttachmentExtractionModel(SQLModel, table=True):
    __tablename__ = "attachment_extraction"  # type: ignore
    __table_args__ = (
        UniqueConstraint(
            "attachment_file_id",
            "prompt_version",
            name="uq_attachment_extraction_file_prompt",
        ),
        CheckConstraint(
            "input_mode IN ('inline','files_api','text','reused')",
            name="ck_attachment_extraction_input_mode",
        ),
        CheckConstraint(
            "citas_verificadas >= 0 AND citas_verificadas <= citas_total",
            name="ck_attachment_extraction_citas",
        ),
        Index(
            "ix_attachment_extraction_reuse",
            "tender_attachment_id",
            "sha256",
            "prompt_version",
        ),
        Index("ix_attachment_extraction_tender_id", "tender_id"),
    )

    id: UUID = Field(primary_key=True)
    attachment_file_id: UUID = Field(
        foreign_key="attachment_file.id", ondelete="CASCADE"
    )
    tender_attachment_id: UUID = Field(
        foreign_key="tender_attachment.id", ondelete="CASCADE"
    )
    tender_id: UUID = Field(foreign_key="tender.id", ondelete="CASCADE")
    sha256: str = Field(max_length=64)
    prompt_version: str = Field(max_length=40)
    model: str = Field(max_length=100)
    input_mode: str = Field(max_length=20)
    data: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    citas_total: int
    citas_verificadas: int
    texto_disponible: bool
    usage_metadata: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    reused_from_id: UUID | None = Field(default=None)
    created_at: datetime


class TenderDigestModel(SQLModel, table=True):
    __tablename__ = "tender_digest"  # type: ignore
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_tender_digest_version"),
        CheckConstraint(
            "source_count >= 0", name="ck_tender_digest_source_count"
        ),
        Index("ix_tender_digest_tender_id", "tender_id"),
        Index("ix_tender_digest_workspace_id", "workspace_id"),
        Index(
            "uq_tender_digest_current_shared",
            "tender_id",
            unique=True,
            postgresql_where=text("is_current AND workspace_id IS NULL"),
        ),
        Index(
            "uq_tender_digest_current_workspace",
            "tender_id",
            "workspace_id",
            unique=True,
            postgresql_where=text("is_current AND workspace_id IS NOT NULL"),
        ),
    )

    id: UUID = Field(primary_key=True)
    tender_id: UUID = Field(foreign_key="tender.id", ondelete="CASCADE")
    workspace_id: UUID | None = Field(
        default=None, foreign_key="supplier.id", ondelete="CASCADE"
    )
    version: int
    extraction_set_hash: str = Field(max_length=64)
    is_current: bool
    source_count: int
    data: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    api_snapshot: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime


class AttachmentGeminiDailyUsageModel(SQLModel, table=True):
    __tablename__ = "attachment_gemini_daily_usage"  # type: ignore
    __table_args__ = (
        CheckConstraint(
            "calls >= 0", name="ck_attachment_gemini_daily_usage_calls"
        ),
    )

    day: date = Field(primary_key=True)
    calls: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    prompt_tokens: int = Field(
        default=0,
        sa_column=Column(BigInteger, nullable=False, server_default="0"),
    )
    output_tokens: int = Field(
        default=0,
        sa_column=Column(BigInteger, nullable=False, server_default="0"),
    )
