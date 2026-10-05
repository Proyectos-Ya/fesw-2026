"""Entidad de tarea de extracción distribuida para la extensión (Plan 233, Decisión 7)."""

from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.shared.datetime_utils import UtcDateTime, utc_now_naive

JobStatus = Literal["pending", "leased", "completed", "failed", "skipped"]


class ExtensionFetchJob(BaseModel):
    """Tarea de la cola distribuida de extracción de anexos comunitarios."""

    id: UUID = Field(default_factory=uuid4)
    tender_id: UUID
    tender_code: str
    status: JobStatus = "pending"
    priority: int = 0
    leased_to_installation_id: UUID | None = None
    leased_at: UtcDateTime | None = None
    lease_expires_at: UtcDateTime | None = None
    attempts: int = 0
    max_attempts: int = 3
    error_code: str | None = None
    error_detail: str | None = None
    result_summary: dict[str, Any] | None = None
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)
    updated_at: UtcDateTime = Field(default_factory=utc_now_naive)
