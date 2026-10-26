"""Tests unitarios para ScheduleTenderDigestsUseCase y RefreshDigestsOnShared (plan 233, decisión 4)."""

from datetime import datetime
from uuid import uuid4

import pytest

from app.application.services.digest_refresh_listener import (
    RefreshDigestsOnShared,
)
from app.application.use_cases.attachment_processing.schedule_tender_digests import (
    ScheduleTenderDigestsUseCase,
)
from app.domain.entities.attachment_file import (
    AttachmentVisibility,
)
from app.domain.entities.attachment_processing import (
    PRIORIDAD_RESUMEN,
    ProcessingJobKind,
)
from app.domain.entities.tender_digest import (
    TenderDigest,
    TenderDigestData,
)
from tests.unit.application.attachment_processing_fakes import (
    Reloj,
    mundo,
)

AHORA = datetime(2026, 10, 3, 15, 0)


@pytest.mark.asyncio
async def test_for_extracted_file_privado_encola_para_empresa():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    caso = ScheduleTenderDigestsUseCase(
        jobs=m.jobs,
        digests=m.digests,
        notifier=m.notifier,
        clock=reloj,
    )

    await caso.for_extracted_file(m.archivo)

    assert m.notifier.avisos == 1
    jobs = list(m.jobs.filas.values())
    assert len(jobs) == 1
    assert jobs[0].kind == ProcessingJobKind.DIGEST
    assert jobs[0].tender_id == m.tender.id
    assert jobs[0].workspace_id == m.ws_a
    assert jobs[0].priority == PRIORIDAD_RESUMEN


@pytest.mark.asyncio
async def test_for_extracted_file_compartido_encola_compartido_y_empresas():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    m.archivo.visibility = AttachmentVisibility.SHARED
    m.archivo.workspace_id = None

    # WS_B tiene un digest vigente
    digest_b = TenderDigest(
        id=uuid4(),
        tender_id=m.tender.id,
        workspace_id=m.ws_b,
        version=1,
        extraction_set_hash="hash_b",
        is_current=True,
        source_count=1,
        data=TenderDigestData.vacio(),
        api_snapshot={},
        created_at=AHORA,
    )
    m.digests.filas[digest_b.id] = digest_b

    caso = ScheduleTenderDigestsUseCase(
        jobs=m.jobs,
        digests=m.digests,
        notifier=m.notifier,
        clock=reloj,
    )

    await caso.for_extracted_file(m.archivo)

    assert m.notifier.avisos == 1
    digest_jobs = [
        j
        for j in m.jobs.filas.values()
        if j.kind == ProcessingJobKind.DIGEST
    ]
    workspaces = {j.workspace_id for j in digest_jobs}
    assert workspaces == {None, m.ws_b}


@pytest.mark.asyncio
async def test_refresh_digests_on_shared_listener():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    caso = ScheduleTenderDigestsUseCase(
        jobs=m.jobs,
        digests=m.digests,
        notifier=m.notifier,
        clock=reloj,
    )
    listener = RefreshDigestsOnShared(caso)

    m.archivo.visibility = AttachmentVisibility.SHARED
    await listener.on_visibility_changed(m.archivo)

    assert m.notifier.avisos == 1
    digest_jobs = [
        j
        for j in m.jobs.filas.values()
        if j.kind == ProcessingJobKind.DIGEST
    ]
    assert len(digest_jobs) == 1
    assert digest_jobs[0].workspace_id is None
