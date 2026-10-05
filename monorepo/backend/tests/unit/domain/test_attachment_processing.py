"""Tests de la cola de procesamiento de anexos y estados (plan 233, decisión 4)."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
    AttachmentTrust,
    AttachmentVisibility,
)
from app.domain.entities.attachment_processing import (
    HANDLED_KINDS,
    MAX_INTENTOS,
    MOTIVOS_DE_RECHAZO,
    AttachmentProcessingJob,
    EstadoDeExtraccion,
    MotivoDeEstado,
    ProcessingJobKind,
    ProcessingJobStatus,
    ProcessingState,
    agoto_intentos,
    estado_de_procesamiento,
    proximo_intento,
)

AHORA = datetime(2026, 10, 3, 15, 0)


def test_esperas_proximo_intento():
    assert proximo_intento(ProcessingJobKind.EXTRACT, 1, AHORA) == AHORA + timedelta(minutes=5)
    assert proximo_intento(ProcessingJobKind.EXTRACT, 2, AHORA) == AHORA + timedelta(minutes=30)
    assert proximo_intento(ProcessingJobKind.EXTRACT, 3, AHORA) == AHORA + timedelta(minutes=30)

    assert proximo_intento(ProcessingJobKind.DIGEST, 1, AHORA) == AHORA + timedelta(minutes=1)
    assert proximo_intento(ProcessingJobKind.DIGEST, 2, AHORA) == AHORA + timedelta(minutes=5)
    assert proximo_intento(ProcessingJobKind.DIGEST, 3, AHORA) == AHORA + timedelta(minutes=15)
    assert proximo_intento(ProcessingJobKind.DIGEST, 4, AHORA) == AHORA + timedelta(hours=1)
    assert proximo_intento(ProcessingJobKind.DIGEST, 9, AHORA) == AHORA + timedelta(hours=1)


def test_agoto_intentos():
    def _trabajo(kind: ProcessingJobKind, attempts: int) -> AttachmentProcessingJob:
        return AttachmentProcessingJob(
            id=uuid4(),
            kind=kind,
            status=ProcessingJobStatus.RUNNING,
            priority=0,
            attempts=attempts,
            not_before=AHORA,
            tender_id=uuid4(),
            created_at=AHORA,
            updated_at=AHORA,
        )

    assert agoto_intentos(_trabajo(ProcessingJobKind.EXTRACT, 2)) is False
    assert agoto_intentos(_trabajo(ProcessingJobKind.EXTRACT, 3)) is True
    assert agoto_intentos(_trabajo(ProcessingJobKind.EXTRACT, 4)) is True

    assert agoto_intentos(_trabajo(ProcessingJobKind.DIGEST, 4)) is False
    assert agoto_intentos(_trabajo(ProcessingJobKind.DIGEST, 5)) is True


def test_handled_kinds_no_incluye_shadow_score():
    assert HANDLED_KINDS == (ProcessingJobKind.EXTRACT, ProcessingJobKind.DIGEST)
    assert ProcessingJobKind.SHADOW_SCORE not in HANDLED_KINDS


def test_motivos_de_rechazo():
    assert MotivoDeEstado.CHECKSUM_MISMATCH in MOTIVOS_DE_RECHAZO
    assert MotivoDeEstado.CONTENT_MISMATCH in MOTIVOS_DE_RECHAZO
    assert MotivoDeEstado.MACRO_ENABLED in MOTIVOS_DE_RECHAZO
    assert MotivoDeEstado.ARCHIVE_TOO_LARGE in MOTIVOS_DE_RECHAZO
    assert MotivoDeEstado.LEGACY_FORMAT not in MOTIVOS_DE_RECHAZO
    assert MotivoDeEstado.FORMAT_NOT_SUPPORTED not in MOTIVOS_DE_RECHAZO


def _crear_archivo(status: AttachmentFileStatus) -> AttachmentFile:
    ws_id = uuid4()
    return AttachmentFile(
        id=uuid4(),
        tender_attachment_id=uuid4(),
        tender_id=uuid4(),
        sha256="a" * 64,
        size_bytes=1000,
        storage_key="test/key",
        source=AttachmentFileSource.MANUAL,
        uploader_user_id=uuid4(),
        workspace_id=ws_id,
        visibility=AttachmentVisibility.PRIVATE,
        trust=AttachmentTrust.PENDING,
        status=status,
        created_at=AHORA,
    )


def test_estado_de_procesamiento():
    # Sin archivo
    assert estado_de_procesamiento(None, None) is None

    # Archivo UNSUPPORTED
    unsupported_file = _crear_archivo(AttachmentFileStatus.UNSUPPORTED)
    assert estado_de_procesamiento(unsupported_file, None) == ProcessingState.UNSUPPORTED

    # Estados no procesables
    for st in (AttachmentFileStatus.UPLOADING, AttachmentFileStatus.REJECTED, AttachmentFileStatus.PURGED):
        file = _crear_archivo(st)
        assert estado_de_procesamiento(file, None) is None
        assert estado_de_procesamiento(file, EstadoDeExtraccion(extraida=True, fallida=False)) is None

    # STORED
    stored_file = _crear_archivo(AttachmentFileStatus.STORED)
    # sin señal
    assert estado_de_procesamiento(stored_file, None) == ProcessingState.PROCESSING
    assert estado_de_procesamiento(stored_file, EstadoDeExtraccion(extraida=False, fallida=False)) == ProcessingState.PROCESSING
    # extraída
    assert estado_de_procesamiento(stored_file, EstadoDeExtraccion(extraida=True, fallida=False)) == ProcessingState.READY
    # fallida
    assert estado_de_procesamiento(stored_file, EstadoDeExtraccion(extraida=False, fallida=True)) == ProcessingState.FAILED
    # extraída gana sobre fallida
    assert estado_de_procesamiento(stored_file, EstadoDeExtraccion(extraida=True, fallida=True)) == ProcessingState.READY
