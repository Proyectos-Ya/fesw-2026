"""Tests unitarios para ProcessNextAttachmentJobUseCase (plan 233, decisión 4)."""

from datetime import date, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
import respx

from app.application.use_cases.attachment_processing.extract_attachment import (
    ExtractAttachmentUseCase,
)
from app.application.use_cases.attachment_processing.process_next_job import (
    ProcessNextAttachmentJobUseCase,
)
from app.domain.entities.attachment_extraction import EXTRACTION_PROMPT_VERSION
from app.domain.entities.attachment_file import AttachmentVisibility
from app.domain.entities.attachment_processing import (
    PRIORIDAD_RESUMEN,
    PRIORIDAD_SUBIDA_MANUAL,
    AttachmentProcessingJob,
    ProcessingJobKind,
    ProcessingJobStatus,
)
from app.domain.entities.tender_digest import (
    TenderDigest,
    TenderDigestData,
)
from app.infrastructure.services.attachments.content_reader import (
    StdlibAttachmentContentReader,
)
from app.infrastructure.services.attachments.gemini_attachment_extraction_service import (
    GeminiAttachmentExtractionService,
)
from tests.unit.application.attachment_processing_fakes import (
    EXTRACCION_SIN_CITAS,
    EXTRACCION_VALIDA,
    GEN_URL,
    Reloj,
    mundo,
    respuesta_gemini,
)

AHORA = datetime(2026, 10, 3, 15, 0)
DIA = date(2026, 10, 3)


def _crear_caso_uso(
    m,
    *,
    reloj: Reloj,
    daily_budget: int = 100,
) -> ProcessNextAttachmentJobUseCase:
    ai = GeminiAttachmentExtractionService(
        api_key="clave-test",
        model_name="gemini-test",
    )
    reader = StdlibAttachmentContentReader()
    extract = ExtractAttachmentUseCase(
        units=m.units,
        storage=m.storage,
        reader=reader,
        ai=ai,
        daily_budget=daily_budget,
        prompt_version=EXTRACTION_PROMPT_VERSION,
        clock=reloj,
    )
    return ProcessNextAttachmentJobUseCase(
        units=m.units,
        extract=extract,
        notifier=m.notifier,
        clock=reloj,
    )


@respx.mock
@pytest.mark.asyncio
async def test_respuesta_sin_citas_se_rechaza_y_reintenta():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    ruta = respx.post(GEN_URL).mock(
        side_effect=[
            httpx.Response(200, json=respuesta_gemini(EXTRACCION_SIN_CITAS)),
            httpx.Response(200, json=respuesta_gemini(EXTRACCION_VALIDA)),
        ]
    )

    await m.jobs.enqueue_extract(
        attachment_file_id=m.archivo.id,
        tender_id=m.tender.id,
        priority=PRIORIDAD_SUBIDA_MANUAL,
        now=reloj(),
    )
    job_id = list(m.jobs.filas.keys())[0]
    caso = _crear_caso_uso(m, reloj=reloj)

    # 1. Primera ejecución: falla por falta de citas
    res = await caso.execute()
    assert res is True
    job = m.jobs.filas[job_id]
    assert job.status == ProcessingJobStatus.PENDING
    assert job.attempts == 1
    assert "sin citas" in (job.last_error or "")
    assert job.not_before == AHORA + timedelta(minutes=5)
    assert len(m.extractions.filas) == 0

    # 2. Con el reloj en AHORA + 4 min, no procesa
    reloj.avanzar(timedelta(minutes=4))
    res = await caso.execute()
    assert res is False

    # 3. Con el reloj en AHORA + 5 min, procesa y completa
    reloj.avanzar(timedelta(minutes=1))
    res = await caso.execute()
    assert res is True
    job = m.jobs.filas[job_id]
    assert job.status == ProcessingJobStatus.DONE
    assert len(m.extractions.filas) == 1

    # Encoló digest para (tender, ws_a) con prioridad 20
    digest_jobs = [
        j
        for j in m.jobs.filas.values()
        if j.kind == ProcessingJobKind.DIGEST
    ]
    assert len(digest_jobs) == 1
    assert digest_jobs[0].tender_id == m.tender.id
    assert digest_jobs[0].workspace_id == m.ws_a
    assert digest_jobs[0].priority == PRIORIDAD_RESUMEN

    assert await m.usage.calls_on(DIA) == 2
    assert ruta.call_count == 2


@respx.mock
@pytest.mark.asyncio
async def test_tres_fallos_dejan_el_trabajo_fallido():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    respx.post(GEN_URL).respond(200, json=respuesta_gemini(EXTRACCION_SIN_CITAS))

    await m.jobs.enqueue_extract(
        attachment_file_id=m.archivo.id,
        tender_id=m.tender.id,
        priority=PRIORIDAD_SUBIDA_MANUAL,
        now=reloj(),
    )
    job_id = list(m.jobs.filas.keys())[0]
    caso = _crear_caso_uso(m, reloj=reloj)

    # Intento 1
    await caso.execute()
    job = m.jobs.filas[job_id]
    assert job.status == ProcessingJobStatus.PENDING
    assert job.attempts == 1

    # Intento 2
    reloj.avanzar(timedelta(minutes=6))
    await caso.execute()
    job = m.jobs.filas[job_id]
    assert job.status == ProcessingJobStatus.PENDING
    assert job.attempts == 2

    # Intento 3: se agotan intentos (MAX_INTENTOS=3) -> FAILED
    reloj.avanzar(timedelta(minutes=31))
    await caso.execute()
    job = m.jobs.filas[job_id]
    assert job.status == ProcessingJobStatus.FAILED
    assert job.attempts == 3


@respx.mock(assert_all_called=False)
@pytest.mark.asyncio
async def test_tope_agotado_difiere_sin_gastar_intento(respx_mock):
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    ruta = respx_mock.post(GEN_URL).respond(200, json=respuesta_gemini(EXTRACCION_VALIDA))
    await m.usage.try_reserve_call(day=DIA, limit=1)

    await m.jobs.enqueue_extract(
        attachment_file_id=m.archivo.id,
        tender_id=m.tender.id,
        priority=PRIORIDAD_SUBIDA_MANUAL,
        now=reloj(),
    )
    job_id = list(m.jobs.filas.keys())[0]
    caso = _crear_caso_uso(m, reloj=reloj, daily_budget=1)

    res = await caso.execute()
    assert res is True
    job = m.jobs.filas[job_id]
    assert job.status == ProcessingJobStatus.PENDING
    assert job.attempts == 0
    assert job.not_before == datetime(2026, 10, 4, 3, 0)
    assert job.last_error is not None
    assert job.last_error.startswith("Tope diario de Gemini agotado")
    assert ruta.call_count == 0


@respx.mock
@pytest.mark.asyncio
async def test_429_difiere_sin_gastar_intento():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    respx.post(GEN_URL).respond(429, headers={"Retry-After": "120"})

    await m.jobs.enqueue_extract(
        attachment_file_id=m.archivo.id,
        tender_id=m.tender.id,
        priority=PRIORIDAD_SUBIDA_MANUAL,
        now=reloj(),
    )
    job_id = list(m.jobs.filas.keys())[0]
    caso = _crear_caso_uso(m, reloj=reloj)

    res = await caso.execute()
    assert res is True
    job = m.jobs.filas[job_id]
    assert job.status == ProcessingJobStatus.PENDING
    assert job.attempts == 0
    assert job.not_before == AHORA + timedelta(seconds=120)


@respx.mock
@pytest.mark.asyncio
async def test_400_falla_sin_reintentar():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    respx.post(GEN_URL).respond(400, text="Bad Request")

    await m.jobs.enqueue_extract(
        attachment_file_id=m.archivo.id,
        tender_id=m.tender.id,
        priority=PRIORIDAD_SUBIDA_MANUAL,
        now=reloj(),
    )
    job_id = list(m.jobs.filas.keys())[0]
    caso = _crear_caso_uso(m, reloj=reloj)

    res = await caso.execute()
    assert res is True
    job = m.jobs.filas[job_id]
    assert job.status == ProcessingJobStatus.FAILED


@respx.mock
@pytest.mark.asyncio
async def test_archivo_compartido_encola_el_resumen_compartido_y_los_de_empresa():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    respx.post(GEN_URL).respond(200, json=respuesta_gemini(EXTRACCION_VALIDA))

    # El archivo es SHARED
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

    await m.jobs.enqueue_extract(
        attachment_file_id=m.archivo.id,
        tender_id=m.tender.id,
        priority=PRIORIDAD_SUBIDA_MANUAL,
        now=reloj(),
    )
    caso = _crear_caso_uso(m, reloj=reloj)

    await caso.execute()

    digest_jobs = [
        j
        for j in m.jobs.filas.values()
        if j.kind == ProcessingJobKind.DIGEST
    ]
    # Encoló digest para compartido (None) y para WS_B
    workspaces = {j.workspace_id for j in digest_jobs}
    assert workspaces == {None, m.ws_b}


@respx.mock(assert_all_called=False)
@pytest.mark.asyncio
async def test_rechazado_o_no_soportado_no_encola_resumen(respx_mock):
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    # Checksum mismatch
    m.storage.objetos[m.archivo.storage_key] = b"basura"

    await m.jobs.enqueue_extract(
        attachment_file_id=m.archivo.id,
        tender_id=m.tender.id,
        priority=PRIORIDAD_SUBIDA_MANUAL,
        now=reloj(),
    )
    job_id = list(m.jobs.filas.keys())[0]
    caso = _crear_caso_uso(m, reloj=reloj)

    res = await caso.execute()
    assert res is True
    job = m.jobs.filas[job_id]
    assert job.status == ProcessingJobStatus.DONE
    digest_jobs = [
        j
        for j in m.jobs.filas.values()
        if j.kind == ProcessingJobKind.DIGEST
    ]
    assert len(digest_jobs) == 0


@pytest.mark.asyncio
async def test_digest_construye_y_completa():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)

    await m.jobs.enqueue_digest(
        tender_id=m.tender.id,
        workspace_id=None,
        priority=PRIORIDAD_RESUMEN,
        now=reloj(),
    )
    job_id = list(m.jobs.filas.keys())[0]
    caso = _crear_caso_uso(m, reloj=reloj)

    res = await caso.execute()
    assert res is True
    job = m.jobs.filas[job_id]
    assert job.status == ProcessingJobStatus.DONE


@pytest.mark.asyncio
async def test_no_toma_shadow_score():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)

    job_shadow = AttachmentProcessingJob(
        id=uuid4(),
        kind=ProcessingJobKind.SHADOW_SCORE,
        status=ProcessingJobStatus.PENDING,
        priority=0,
        attempts=0,
        not_before=AHORA,
        tender_id=m.tender.id,
        created_at=AHORA,
        updated_at=AHORA,
    )
    m.jobs.filas[job_shadow.id] = job_shadow
    caso = _crear_caso_uso(m, reloj=reloj)

    res = await caso.execute()
    assert res is False
    assert m.jobs.filas[job_shadow.id].status == ProcessingJobStatus.PENDING


@respx.mock
@pytest.mark.asyncio
async def test_un_error_inesperado_reintenta():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    respx.post(GEN_URL).respond(200, json=respuesta_gemini(EXTRACCION_VALIDA))

    # Hacer que create() lance RuntimeError
    async def _falla_create(extraccion):
        raise RuntimeError("Fallo inesperado de DB")

    m.extractions.create = _falla_create

    await m.jobs.enqueue_extract(
        attachment_file_id=m.archivo.id,
        tender_id=m.tender.id,
        priority=PRIORIDAD_SUBIDA_MANUAL,
        now=reloj(),
    )
    job_id = list(m.jobs.filas.keys())[0]
    caso = _crear_caso_uso(m, reloj=reloj)

    res = await caso.execute()
    assert res is True
    job = m.jobs.filas[job_id]
    assert job.status == ProcessingJobStatus.PENDING
    assert job.attempts == 1
