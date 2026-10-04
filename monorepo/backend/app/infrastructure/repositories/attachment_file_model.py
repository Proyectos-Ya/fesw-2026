"""Archivos subidos para los anexos oficiales y cupo mensual por empresa (plan 233, decisión 2).

Sin `index=True`: los índices van en `__table_args__` con el nombre exacto de la
migración, para que `alembic check` no proponga renombrarlos. Los CHECK no los
compara Alembic: se declaran igual para que `create_all` (tests de integración)
también los imponga. `server_default` va declarado porque `compare_server_default`
está activo.

Texto con CHECK y no ENUM nativo: `status`, `visibility` y `trust` gobiernan qué ve
cada empresa, así que un valor inválido no puede entrar, y agregar un valor a un
ENUM de Postgres no se revierte en un downgrade mientras que un CHECK se reemplaza.
Los conjuntos completos ya están (incluidos los de las decisiones 5, 6 y 7).
"""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, Column, Index, UniqueConstraint
from sqlmodel import Field, SQLModel

_ESTADOS = "'uploading','stored','unsupported','rejected','purged'"


class AttachmentFileModel(SQLModel, table=True):
    __tablename__ = "attachment_file"  # type: ignore
    __table_args__ = (
        # Un archivo por (anexo, contenido, empresa): el reintento reutiliza la fila.
        # Su índice empieza por tender_attachment_id y ya cubre esa FK.
        UniqueConstraint(
            "tender_attachment_id",
            "sha256",
            "workspace_id",
            name="uq_attachment_file_attachment_sha_workspace",
        ),
        Index("ix_attachment_file_tender_id", "tender_id"),
        # Cubre la FK de empresa y la deduplicación por objeto.
        Index("ix_attachment_file_workspace_sha", "workspace_id", "sha256"),
        Index("ix_attachment_file_uploader_user_id", "uploader_user_id"),
        CheckConstraint(f"status IN ({_ESTADOS})", name="ck_attachment_file_status"),
        CheckConstraint(
            "visibility IN ('private','shared')", name="ck_attachment_file_visibility"
        ),
        CheckConstraint(
            "trust IN ('pending','corroborated','conflict','rejected')",
            name="ck_attachment_file_trust",
        ),
        CheckConstraint(
            "source IN ('manual','extension','legacy_chat')",
            name="ck_attachment_file_source",
        ),
        CheckConstraint("size_bytes > 0", name="ck_attachment_file_size"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_attachment_file_sha256"),
    )

    id: UUID = Field(primary_key=True)
    tender_attachment_id: UUID = Field(
        foreign_key="tender_attachment.id", ondelete="CASCADE"
    )
    tender_id: UUID = Field(foreign_key="tender.id", ondelete="CASCADE")
    sha256: str = Field(max_length=64)
    size_bytes: int = Field(sa_column=Column(BigInteger, nullable=False))
    mime_declared: str | None = Field(default=None, max_length=255)
    storage_key: str = Field(max_length=512)
    source: str = Field(max_length=20)
    # El archivo es de la empresa, no de la persona: si se borra el usuario, queda sin autor.
    uploader_user_id: UUID | None = Field(
        default=None, foreign_key="users.id", ondelete="SET NULL"
    )
    workspace_id: UUID = Field(foreign_key="supplier.id", ondelete="CASCADE")
    visibility: str = Field(
        default="private", max_length=20, sa_column_kwargs={"server_default": "private"}
    )
    trust: str = Field(
        default="pending", max_length=20, sa_column_kwargs={"server_default": "pending"}
    )
    status: str = Field(max_length=20)
    created_at: datetime
    completed_at: datetime | None = Field(default=None)
    purge_after: datetime | None = Field(default=None)


class AttachmentUploadQuotaModel(SQLModel, table=True):
    """Subidas nuevas de una empresa en un mes de calendario de Chile."""

    __tablename__ = "attachment_upload_quota"  # type: ignore
    __table_args__ = (
        CheckConstraint("used >= 0", name="ck_attachment_upload_quota_used"),
    )

    # La PK compuesta empieza por workspace_id: cubre también el índice de la FK.
    workspace_id: UUID = Field(
        primary_key=True, foreign_key="supplier.id", ondelete="CASCADE"
    )
    month: date = Field(primary_key=True)  # día 1 del mes de Chile
    used: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
