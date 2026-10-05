"""Tests unitarios para EnqueueExtractionOnStored (plan 233, decisión 4)."""

from datetime import datetime

import pytest

from app.application.services.attachment_stored_listener import (
    CompositeAttachmentStoredListener,
    IAttachmentStoredListener,
)
from app.application.services.enqueue_extraction_listener import (
    EnqueueExtractionOnStored,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
)
from app.domain.entities.attachment_processing import (
    PRIORIDAD_SUBIDA_MANUAL,
    ProcessingJobKind,
)
from tests.unit.application.attachment_processing_fakes import (
    Reloj,
    mundo,
)

AHORA = datetime(2026, 10, 3, 15, 0)


@pytest.mark.asyncio
async def test_encola_con_prioridad_10_y_avisa_una_vez():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    listener = EnqueueExtractionOnStored(
        jobs=m.jobs,
        notifier=m.notifier,
        clock=reloj,
    )

    await listener.on_stored(m.archivo)

    assert m.notifier.avisos == 1
    jobs = list(m.jobs.filas.values())
    assert len(jobs) == 1
    assert jobs[0].kind == ProcessingJobKind.EXTRACT
    assert jobs[0].priority == PRIORIDAD_SUBIDA_MANUAL
    assert jobs[0].attachment_file_id == m.archivo.id


@pytest.mark.asyncio
async def test_llamarlo_dos_veces_deja_un_solo_pendiente_y_un_solo_aviso():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    listener = EnqueueExtractionOnStored(
        jobs=m.jobs,
        notifier=m.notifier,
        clock=reloj,
    )

    await listener.on_stored(m.archivo)
    await listener.on_stored(m.archivo)

    assert m.notifier.avisos == 1
    jobs = list(m.jobs.filas.values())
    assert len(jobs) == 1


@pytest.mark.asyncio
async def test_archivo_unsupported_no_se_encola():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    m.archivo.status = AttachmentFileStatus.UNSUPPORTED
    listener = EnqueueExtractionOnStored(
        jobs=m.jobs,
        notifier=m.notifier,
        clock=reloj,
    )

    await listener.on_stored(m.archivo)

    assert m.notifier.avisos == 0
    assert len(m.jobs.filas) == 0


@pytest.mark.asyncio
async def test_composite_con_listener_que_falla_igual_encola():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    extraction_listener = EnqueueExtractionOnStored(
        jobs=m.jobs,
        notifier=m.notifier,
        clock=reloj,
    )

    class ListenerQueFalla(IAttachmentStoredListener):
        async def on_stored(self, file: AttachmentFile) -> None:
            raise RuntimeError("Fallo simulado en listener previo")

    composite = CompositeAttachmentStoredListener(
        [ListenerQueFalla(), extraction_listener]
    )

    await composite.on_stored(m.archivo)

    assert m.notifier.avisos == 1
    assert len(m.jobs.filas) == 1
