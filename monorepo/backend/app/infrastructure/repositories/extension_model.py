"""Modelos de base de datos SQLModel para la extensión de navegador (Plan 233, Decisión 7)."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.shared.datetime_utils import utc_now_naive


class ExtensionInstallationModel(SQLModel, table=True):
    """Instalación individual de la extensión en el navegador de un usuario."""

    __tablename__ = "extension_installation"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(
        sa_column=sa.Column(
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    workspace_id: UUID | None = Field(
        default=None,
        sa_column=sa.Column(
            sa.Uuid(),
            sa.ForeignKey("supplier.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    browser: str = Field(sa_column=sa.Column(sa.String(32), nullable=False))
    browser_version: str | None = Field(
        default=None, sa_column=sa.Column(sa.String(64), nullable=True)
    )
    extension_version: str = Field(
        sa_column=sa.Column(sa.String(32), nullable=False)
    )
    is_active: bool = Field(
        default=True,
        sa_column=sa.Column(sa.Boolean(), nullable=False, index=True),
    )
    last_heartbeat_at: datetime | None = Field(
        default=None, sa_column=sa.Column(sa.DateTime(), nullable=True)
    )
    created_at: datetime = Field(
        default_factory=utc_now_naive,
        sa_column=sa.Column(sa.DateTime(), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now_naive,
        sa_column=sa.Column(sa.DateTime(), nullable=False),
    )


class ExtensionFetchJobModel(SQLModel, table=True):
    """Tarea de extracción distribuida en la cola."""

    __tablename__ = "extension_fetch_job"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tender_id: UUID = Field(
        sa_column=sa.Column(
            sa.Uuid(),
            sa.ForeignKey("tenders.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    tender_code: str = Field(
        sa_column=sa.Column(sa.String(64), nullable=False, index=True)
    )
    status: str = Field(
        default="pending",
        sa_column=sa.Column(sa.String(32), nullable=False, index=True),
    )
    priority: int = Field(
        default=0, sa_column=sa.Column(sa.Integer(), nullable=False, index=True)
    )
    leased_to_installation_id: UUID | None = Field(
        default=None,
        sa_column=sa.Column(
            sa.Uuid(),
            sa.ForeignKey("extension_installation.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    leased_at: datetime | None = Field(
        default=None, sa_column=sa.Column(sa.DateTime(), nullable=True)
    )
    lease_expires_at: datetime | None = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(), nullable=True, index=True),
    )
    attempts: int = Field(
        default=0, sa_column=sa.Column(sa.Integer(), nullable=False)
    )
    max_attempts: int = Field(
        default=3, sa_column=sa.Column(sa.Integer(), nullable=False)
    )
    error_code: str | None = Field(
        default=None, sa_column=sa.Column(sa.String(64), nullable=True)
    )
    error_detail: str | None = Field(
        default=None, sa_column=sa.Column(sa.Text(), nullable=True)
    )
    result_summary: dict[str, Any] | None = Field(
        default=None,
        sa_column=sa.Column(JSONB, nullable=True),
    )
    created_at: datetime = Field(
        default_factory=utc_now_naive,
        sa_column=sa.Column(sa.DateTime(), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now_naive,
        sa_column=sa.Column(sa.DateTime(), nullable=False),
    )

    __table_args__ = (
        sa.Index(
            "ix_extension_fetch_job_queue",
            "status",
            sa.text("priority DESC"),
            "lease_expires_at",
            "created_at",
        ),
        sa.Index(
            "uq_extension_fetch_job_active_tender",
            "tender_id",
            unique=True,
            postgresql_where=sa.text("status IN ('pending', 'leased')"),
        ),
    )
