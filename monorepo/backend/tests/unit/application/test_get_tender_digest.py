"""Tests unitarios para GetTenderDigestUseCase (plan 233, decisión 4)."""

from copy import deepcopy
from datetime import datetime
from uuid import uuid4

import pytest

from app.application.use_cases.attachment_processing.build_tender_digest import (
    BuildTenderDigestUseCase,
)
from app.application.use_cases.attachment_processing.get_tender_digest import (
    GetTenderDigestUseCase,
)
from app.domain.entities.attachment_extraction import (
    EXTRACTION_PROMPT_VERSION,
    AttachmentExtraction,
    AttachmentExtractionData,
    ExtractionInputMode,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
    AttachmentTrust,
    AttachmentVisibility,
)
from app.domain.entities.attachment_processing import (
    PRIORIDAD_SUBIDA_MANUAL,
    ProcessingJobKind,
)
from app.domain.errors.tender_errors import TenderNotFound
from tests.unit.application.attachment_processing_fakes import (
    EXTRACCION_VALIDA,
    Reloj,
    mundo,
)

AHORA = datetime(2026, 10, 3, 15, 0)


def _crear_caso_uso(m, reloj: Reloj) -> GetTenderDigestUseCase:
    build = BuildTenderDigestUseCase(
        tenders=m.tenders,
        extractions=m.extractions,
        digests=m.digests,
        prompt_version=EXTRACTION_PROMPT_VERSION,
        clock=reloj,
    )
    return GetTenderDigestUseCase(
        tenders=m.tenders,
        extractions=m.extractions,
        status=m.status_reader,
        build=build,
        prompt_version=EXTRACTION_PROMPT_VERSION,
    )


async def _agregar_extraccion(
    m,
    *,
    archivo: AttachmentFile,
    data: dict | AttachmentExtractionData,
    reloj: Reloj,
) -> AttachmentExtraction:
    data_obj = (
        AttachmentExtractionData.model_validate(data)
        if isinstance(data, dict)
        else data
    )
    ext = AttachmentExtraction(
        id=uuid4(),
        attachment_file_id=archivo.id,
        tender_attachment_id=archivo.tender_attachment_id,
        tender_id=m.tender.id,
        sha256=archivo.sha256,
        prompt_version=EXTRACTION_PROMPT_VERSION,
        model="gemini-test-001",
        input_mode=ExtractionInputMode.INLINE,
        usage_metadata=None,
        citas_total=len(list(data_obj.todas_las_citas())),
        citas_verificadas=0,
        texto_disponible=True,
        data=data_obj,
        created_at=reloj(),
    )
    return await m.extractions.create(ext)


@pytest.mark.asyncio
async def test_otra_empresa_no_ve_los_privados():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)

    # 1. Extracción privada de WS_A con "SECRETO DE A"
    data_a = deepcopy(EXTRACCION_VALIDA)
    data_a["requisitos"].append(
        {
            "descripcion": "SECRETO DE A",
            "tipo": "tecnico",
            "obligatorio": True,
            "citas": [
                {
                    "documento": "Bases.pdf",
                    "pagina_u_hoja": "1",
                    "cita": "cita a",
                }
            ],
        }
    )
    await _agregar_extraccion(m, archivo=m.archivo, data=data_a, reloj=reloj)

    # 2. Archivo compartido con extracción
    archivo_shared = AttachmentFile(
        id=uuid4(),
        tender_attachment_id=m.anexo_docx.id,
        tender_id=m.tender.id,
        sha256="s" * 64,
        size_bytes=100,
        storage_key="ks",
        source=AttachmentFileSource.MANUAL,
        uploader_user_id=None,
        workspace_id=None,
        visibility=AttachmentVisibility.SHARED,
        trust=AttachmentTrust.CORROBORATED,
        status=AttachmentFileStatus.STORED,
        created_at=AHORA,
    )
    m.files.filas[archivo_shared.id] = archivo_shared
    await _agregar_extraccion(
        m, archivo=archivo_shared, data=EXTRACCION_VALIDA, reloj=reloj
    )

    caso = _crear_caso_uso(m, reloj)
    view = await caso.execute(m.tender.id, workspace_id=m.ws_b)

    assert view.scope == "shared"
    assert view.digest is not None
    assert "SECRETO DE A" not in view.digest.data.model_dump_json()
    assert len(view.digest.data.fuentes) == 1
    assert view.digest.data.fuentes[0].archivo_id == archivo_shared.id


@pytest.mark.asyncio
async def test_la_empresa_ve_lo_suyo_y_lo_compartido():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)

    data_a = deepcopy(EXTRACCION_VALIDA)
    await _agregar_extraccion(m, archivo=m.archivo, data=data_a, reloj=reloj)

    archivo_shared = AttachmentFile(
        id=uuid4(),
        tender_attachment_id=m.anexo_docx.id,
        tender_id=m.tender.id,
        sha256="s" * 64,
        size_bytes=100,
        storage_key="ks",
        source=AttachmentFileSource.MANUAL,
        uploader_user_id=None,
        workspace_id=None,
        visibility=AttachmentVisibility.SHARED,
        trust=AttachmentTrust.CORROBORATED,
        status=AttachmentFileStatus.STORED,
        created_at=AHORA,
    )
    m.files.filas[archivo_shared.id] = archivo_shared
    await _agregar_extraccion(
        m, archivo=archivo_shared, data=EXTRACCION_VALIDA, reloj=reloj
    )

    caso = _crear_caso_uso(m, reloj)
    view = await caso.execute(m.tender.id, workspace_id=m.ws_a)

    assert view.scope == "workspace"
    assert view.digest is not None
    assert view.digest.workspace_id == m.ws_a
    assert len(view.digest.data.fuentes) == 2


@pytest.mark.asyncio
async def test_sin_workspace_usa_el_compartido():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    await _agregar_extraccion(
        m, archivo=m.archivo, data=EXTRACCION_VALIDA, reloj=reloj
    )

    archivo_shared = AttachmentFile(
        id=uuid4(),
        tender_attachment_id=m.anexo_docx.id,
        tender_id=m.tender.id,
        sha256="s" * 64,
        size_bytes=100,
        storage_key="ks",
        source=AttachmentFileSource.MANUAL,
        uploader_user_id=None,
        workspace_id=None,
        visibility=AttachmentVisibility.SHARED,
        trust=AttachmentTrust.CORROBORATED,
        status=AttachmentFileStatus.STORED,
        created_at=AHORA,
    )
    m.files.filas[archivo_shared.id] = archivo_shared
    await _agregar_extraccion(
        m, archivo=archivo_shared, data=EXTRACCION_VALIDA, reloj=reloj
    )

    caso = _crear_caso_uso(m, reloj)
    view = await caso.execute(m.tender.id, workspace_id=None)

    assert view.scope == "shared"
    assert view.digest is not None
    assert view.digest.workspace_id is None
    assert len(view.digest.data.fuentes) == 1


@pytest.mark.asyncio
async def test_se_repara_si_cambio_el_conjunto():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)

    # 1. WS_A tiene un privado y se construye su digest
    ext_a = await _agregar_extraccion(
        m, archivo=m.archivo, data=EXTRACCION_VALIDA, reloj=reloj
    )
    caso = _crear_caso_uso(m, reloj)
    view_1 = await caso.execute(m.tender.id, workspace_id=m.ws_a)
    assert view_1.scope == "workspace"

    # 2. Se borra la extracción privada de WS_A
    del m.extractions.filas[ext_a.id]
    del m.files.filas[m.archivo.id]

    view_2 = await caso.execute(m.tender.id, workspace_id=m.ws_a)
    assert view_2.scope == "shared"
    assert view_2.digest is None


@pytest.mark.asyncio
async def test_pendientes():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    # Archivo stored sin extracción y con trabajo encolado
    await m.jobs.enqueue_extract(
        attachment_file_id=m.archivo.id,
        tender_id=m.tender.id,
        priority=PRIORIDAD_SUBIDA_MANUAL,
        now=AHORA,
    )
    caso = _crear_caso_uso(m, reloj)
    view = await caso.execute(m.tender.id, workspace_id=m.ws_a)

    assert view.pending_sources == 1


@pytest.mark.asyncio
async def test_licitacion_inexistente():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    caso = _crear_caso_uso(m, reloj)

    with pytest.raises(TenderNotFound):
        await caso.execute(uuid4(), workspace_id=None)


@pytest.mark.asyncio
async def test_sin_nada_devuelve_vacio():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    m.files.filas.clear()
    caso = _crear_caso_uso(m, reloj)

    view = await caso.execute(m.tender.id, workspace_id=None)

    assert view.digest is None
    assert view.scope == "shared"
    assert view.pending_sources == 0
