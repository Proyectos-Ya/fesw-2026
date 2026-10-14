"""Entidades y funciones de la cola de procesamiento de anexos (plan 233, decisión 4)."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel

from app.domain.entities.attachment_file import AttachmentFile, AttachmentFileStatus


class ProcessingJobKind(StrEnum):
    EXTRACT = "extract"
    DIGEST = "digest"
    SHADOW_SCORE = "shadow_score"  # decisión 9: el CHECK lo admite, nadie lo encola ni lo toma


class ProcessingJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


HANDLED_KINDS: tuple[ProcessingJobKind, ...] = (
    ProcessingJobKind.EXTRACT,
    ProcessingJobKind.DIGEST,
)
PRIORIDAD_RESUMEN = 20  # barato y lo ve el usuario: primero
PRIORIDAD_SUBIDA_MANUAL = 10
PRIORIDAD_EXTENSION = 5  # decisión 7
PRIORIDAD_BARRIDO = 0
MAX_INTENTOS = {
    ProcessingJobKind.EXTRACT: 3,
    ProcessingJobKind.DIGEST: 5,
    ProcessingJobKind.SHADOW_SCORE: 3,
}
ESPERAS = {
    ProcessingJobKind.EXTRACT: (
        timedelta(seconds=10),
        timedelta(minutes=1),
        timedelta(minutes=5),
    ),
    ProcessingJobKind.DIGEST: (
        timedelta(seconds=5),
        timedelta(seconds=30),
        timedelta(minutes=2),
        timedelta(minutes=10),
    ),
    ProcessingJobKind.SHADOW_SCORE: (
        timedelta(seconds=10),
        timedelta(minutes=1),
        timedelta(minutes=5),
    ),
}
PLAZO_DE_TRABAJO_COLGADO = timedelta(minutes=30)  # > 180 s de Gemini + 120 s de subida + parseo
RETENCION_DE_TRABAJOS = timedelta(days=30)  # `done` se purga; `failed` se conserva


class MotivoDeEstado(StrEnum):
    CHECKSUM_MISMATCH = "checksum_mismatch"
    CONTENT_MISMATCH = "content_mismatch"
    MACRO_ENABLED = "macro_enabled"
    ARCHIVE_TOO_LARGE = "archive_too_large"
    LEGACY_FORMAT = "legacy_format"
    ENCRYPTED_OR_LEGACY = "encrypted_or_legacy"
    FORMAT_NOT_SUPPORTED = "format_not_supported"
    NO_TEXT = "no_text"


MOTIVOS_DE_RECHAZO = frozenset(
    {
        MotivoDeEstado.CHECKSUM_MISMATCH,
        MotivoDeEstado.CONTENT_MISMATCH,
        MotivoDeEstado.MACRO_ENABLED,
        MotivoDeEstado.ARCHIVE_TOO_LARGE,
    }
)


class AttachmentProcessingJob(BaseModel):
    id: UUID
    kind: ProcessingJobKind
    status: ProcessingJobStatus
    priority: int = 0
    attempts: int = 0
    last_error: str | None = None
    not_before: datetime
    locked_at: datetime | None = None
    attachment_file_id: UUID | None = None
    tender_id: UUID
    workspace_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


def proximo_intento(kind: ProcessingJobKind, intentos: int, ahora: datetime) -> datetime:
    esperas = ESPERAS[kind]
    return ahora + esperas[min(max(intentos, 1), len(esperas)) - 1]


def agoto_intentos(job: AttachmentProcessingJob) -> bool:
    return job.attempts >= MAX_INTENTOS[job.kind]


class ProcessingState(StrEnum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class EstadoDeExtraccion:
    extraida: bool  # hay extracción para la versión vigente del prompt
    fallida: bool  # el último `extract` terminó en `failed` y no hay otro en curso


def estado_de_procesamiento(
    archivo: AttachmentFile | None, estado: EstadoDeExtraccion | None
) -> ProcessingState | None:
    if archivo is None:
        return None
    if archivo.status == AttachmentFileStatus.UNSUPPORTED:
        return ProcessingState.UNSUPPORTED
    if archivo.status != AttachmentFileStatus.STORED:
        return None
    if estado is not None and estado.extraida:
        return ProcessingState.READY
    if estado is not None and estado.fallida:
        return ProcessingState.FAILED
    return ProcessingState.PROCESSING
