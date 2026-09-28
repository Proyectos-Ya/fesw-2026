"""Exportación que pasó a segundo plano por tardar más de 10 s (HdU 19, criterios 8 y 9)."""

from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.shared.datetime_utils import UtcDateTime

# El enlace del correo sirve una semana, igual que un enlace compartido.
EXPORT_FILE_TTL = timedelta(days=7)


class ExportFormat(StrEnum):
    PDF = "pdf"
    XLSX = "xlsx"

    @property
    def media_type(self) -> str:
        return {
            ExportFormat.PDF: "application/pdf",
            ExportFormat.XLSX: (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        }[self]


class ExportJobStatus(StrEnum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class ExportJob(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    supplier_id: UUID
    tender_id: UUID
    format: ExportFormat
    sections: list[str]
    status: ExportJobStatus = ExportJobStatus.PROCESSING
    file_name: str
    content: bytes | None = None
    error: str | None = None
    created_at: UtcDateTime
    finished_at: UtcDateTime | None = None
    expires_at: UtcDateTime

    @classmethod
    def crear(
        cls,
        user_id: UUID,
        supplier_id: UUID,
        tender_id: UUID,
        format: ExportFormat,
        sections: list[str],
        file_name: str,
        now: datetime,
    ) -> "ExportJob":
        return cls(
            user_id=user_id,
            supplier_id=supplier_id,
            tender_id=tender_id,
            format=format,
            sections=sections,
            file_name=file_name,
            created_at=now,
            expires_at=now + EXPORT_FILE_TTL,
        )

    def listo(self, content: bytes, now: datetime) -> "ExportJob":
        return self.model_copy(
            update={"status": ExportJobStatus.READY, "content": content, "finished_at": now}
        )

    def fallido(self, error: str, now: datetime) -> "ExportJob":
        return self.model_copy(
            update={"status": ExportJobStatus.FAILED, "error": error, "finished_at": now}
        )

    def descargable(self, now: datetime) -> bool:
        return (
            self.status is ExportJobStatus.READY
            and self.content is not None
            and now < self.expires_at
        )
