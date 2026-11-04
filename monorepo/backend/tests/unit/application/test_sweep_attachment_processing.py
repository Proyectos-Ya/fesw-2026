"""Tests unitarios para SweepAttachmentProcessingUseCase (plan 233, decisión 4)."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.application.use_cases.attachment_processing.sweep import (
    SweepAttachmentProcessingUseCase,
)
from app.domain.entities.attachment_extraction import EXTRACTION_PROMPT_VERSION
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
    AttachmentTrust,
    AttachmentVisibility,
)
from app.domain.entities.attachment_processing import (
    PRIORIDAD_BARRIDO,
    AttachmentProcessingJob,
    ProcessingJobKind,
    ProcessingJobStatus,
)
from tests.unit.application.attachment_processing_fakes import (
    Reloj,
    mundo,
)

AHORA = datetime(2026, 10, 3, 15, 0)


@pytest.mark.asyncio
async def test_stored_sin_trabajo_se_encola_con_prioridad_cero_y_notifica():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    caso = SweepAttachmentProcessingUseCase(
        units=m.units,
        notifier=m.notifier,
        prompt_version=EXTRACTION_PROMPT_VERSION,
        clock=reloj,
    )

    resultado = await caso.execute()

    assert resultado.enqueued == 1
    assert m.notifier.avisos == 1
    jobs = list(m.jobs.filas.values())
    assert len(jobs) == 1
    assert jobs[0].kind == ProcessingJobKind.EXTRACT
    assert jobs[0].priority == PRIORIDAD_BARRIDO
    assert jobs[0].attachment_file_id == m.archivo.id


@pytest.mark.asyncio
async def test_con_trabajo_existente_no_se_encola():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    # Ya tiene un trabajo pendiente
    await m.jobs.enqueue_extract(
        attachment_file_id=m.archivo.id,
        tender_id=m.tender.id,
        priority=10,
        now=AHORA,
    )
    m.notifier.avisos = 0
    caso = SweepAttachmentProcessingUseCase(
        units=m.units,
        notifier=m.notifier,
        prompt_version=EXTRACTION_PROMPT_VERSION,
        clock=reloj,
    )

    resultado = await caso.execute()

    assert resultado.enqueued == 0
    assert m.notifier.avisos == 0


@pytest.mark.asyncio
async def test_done_sin_extraccion_de_version_vigente_se_vuelve_a_encolar():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    # Trabajo previo done pero no hay extracción para la versión vigente
    job_viejo = AttachmentProcessingJob(
        id=uuid4(),
        kind=ProcessingJobKind.EXTRACT,
        status=ProcessingJobStatus.DONE,
        priority=10,
        attempts=1,
        not_before=AHORA - timedelta(days=2),
        attachment_file_id=m.archivo.id,
        tender_id=m.tender.id,
        created_at=AHORA - timedelta(days=2),
        updated_at=AHORA - timedelta(days=2),
    )
    m.jobs.filas[job_viejo.id] = job_viejo
    m.notifier.avisos = 0
    caso = SweepAttachmentProcessingUseCase(
        units=m.units,
        notifier=m.notifier,
        prompt_version=EXTRACTION_PROMPT_VERSION,
        clock=reloj,
    )

    resultado = await caso.execute()

    assert resultado.enqueued == 1
    assert m.notifier.avisos == 1


@pytest.mark.asyncio
async def test_running_colgado_recupera_a_pending_o_failed():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)

    # 1. Running colgado con attempts=1 -> pasa a PENDING
    job_colgado_1 = AttachmentProcessingJob(
        id=uuid4(),
        kind=ProcessingJobKind.EXTRACT,
        status=ProcessingJobStatus.RUNNING,
        priority=10,
        attempts=1,
        not_before=AHORA - timedelta(minutes=40),
        locked_at=AHORA - timedelta(minutes=31),
        attachment_file_id=m.archivo.id,
        tender_id=m.tender.id,
        created_at=AHORA - timedelta(minutes=40),
        updated_at=AHORA - timedelta(minutes=31),
    )
    m.jobs.filas[job_colgado_1.id] = job_colgado_1

    # 2. Running colgado con attempts=3 (MAX) -> pasa a FAILED
    otro_archivo = AttachmentFile(
        id=uuid4(),
        tender_attachment_id=m.anexo_docx.id,
        tender_id=m.tender.id,
        sha256="b" * 64,
        size_bytes=100,
        storage_key="k",
        source=AttachmentFileSource.MANUAL,
        uploader_user_id=uuid4(),
        workspace_id=m.ws_a,
        visibility=AttachmentVisibility.PRIVATE,
        trust=AttachmentTrust.PENDING,
        status=AttachmentFileStatus.STORED,
        created_at=AHORA,
    )
    m.files.filas[otro_archivo.id] = otro_archivo
    job_colgado_max = AttachmentProcessingJob(
        id=uuid4(),
        kind=ProcessingJobKind.EXTRACT,
        status=ProcessingJobStatus.RUNNING,
        priority=10,
        attempts=3,
        not_before=AHORA - timedelta(minutes=40),
        locked_at=AHORA - timedelta(minutes=31),
        attachment_file_id=otro_archivo.id,
        tender_id=m.tender.id,
        created_at=AHORA - timedelta(minutes=40),
        updated_at=AHORA - timedelta(minutes=31),
    )
    m.jobs.filas[job_colgado_max.id] = job_colgado_max

    caso = SweepAttachmentProcessingUseCase(
        units=m.units,
        notifier=m.notifier,
        prompt_version=EXTRACTION_PROMPT_VERSION,
        clock=reloj,
    )

    resultado = await caso.execute()

    assert resultado.recovered == 2
    assert m.jobs.filas[job_colgado_1.id].status == ProcessingJobStatus.PENDING
    assert m.jobs.filas[job_colgado_1.id].locked_at is None
    assert m.jobs.filas[job_colgado_max.id].status == ProcessingJobStatus.FAILED


@pytest.mark.asyncio
async def test_done_viejo_se_purga_y_failed_se_conserva():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)

    job_done_viejo = AttachmentProcessingJob(
        id=uuid4(),
        kind=ProcessingJobKind.EXTRACT,
        status=ProcessingJobStatus.DONE,
        priority=10,
        attempts=1,
        not_before=AHORA - timedelta(days=32),
        attachment_file_id=m.archivo.id,
        tender_id=m.tender.id,
        created_at=AHORA - timedelta(days=32),
        updated_at=AHORA - timedelta(days=31),
    )
    job_failed_viejo = AttachmentProcessingJob(
        id=uuid4(),
        kind=ProcessingJobKind.EXTRACT,
        status=ProcessingJobStatus.FAILED,
        priority=10,
        attempts=3,
        not_before=AHORA - timedelta(days=32),
        attachment_file_id=m.archivo.id,
        tender_id=m.tender.id,
        created_at=AHORA - timedelta(days=32),
        updated_at=AHORA - timedelta(days=31),
    )
    m.jobs.filas[job_done_viejo.id] = job_done_viejo
    m.jobs.filas[job_failed_viejo.id] = job_failed_viejo

    caso = SweepAttachmentProcessingUseCase(
        units=m.units,
        notifier=m.notifier,
        prompt_version=EXTRACTION_PROMPT_VERSION,
        clock=reloj,
    )

    resultado = await caso.execute()

    assert resultado.purged == 1
    assert job_done_viejo.id not in m.jobs.filas
    assert job_failed_viejo.id in m.jobs.filas
