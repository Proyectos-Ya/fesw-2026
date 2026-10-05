"""Tests unitarios para BuildTenderDigestUseCase (plan 233, decisión 4)."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.application.use_cases.attachment_processing.build_tender_digest import (
    BuildTenderDigestUseCase,
)
from app.domain.entities.attachment_extraction import (
    EXTRACTION_PROMPT_VERSION,
    AttachmentExtraction,
    AttachmentExtractionData,
    ExtractionInputMode,
    FuenteDeExtraccion,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
    AttachmentTrust,
    AttachmentVisibility,
)
from app.domain.entities.tender_attachment import OfficialAttachment
from app.domain.errors.attachment_processing_errors import FuenteNoVisible
from tests.unit.application.attachment_processing_fakes import (
    EXTRACCION_VALIDA,
    Reloj,
    mundo,
)

AHORA = datetime(2026, 10, 3, 15, 0)


def _crear_caso_uso(m, reloj: Reloj) -> BuildTenderDigestUseCase:
    return BuildTenderDigestUseCase(
        tenders=m.tenders,
        extractions=m.extractions,
        digests=m.digests,
        prompt_version=EXTRACTION_PROMPT_VERSION,
        clock=reloj,
    )


async def _agregar_extraccion(
    m,
    *,
    archivo: AttachmentFile,
    anexo: OfficialAttachment,
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
        tender_attachment_id=anexo.id,
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
async def test_primera_vez_da_version_1():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    # Convertir el archivo a compartido
    m.archivo.visibility = AttachmentVisibility.SHARED
    m.archivo.workspace_id = None
    m.archivo.uploader_user_id = None
    await _agregar_extraccion(
        m,
        archivo=m.archivo,
        anexo=m.anexo_pdf,
        data=EXTRACCION_VALIDA,
        reloj=reloj,
    )

    caso = _crear_caso_uso(m, reloj)
    digest = await caso.execute(m.tender.id, workspace_id=None)

    assert digest is not None
    assert digest.version == 1
    assert digest.is_current is True
    assert digest.source_count == 1
    assert digest.workspace_id is None


@pytest.mark.asyncio
async def test_repetirlo_devuelve_el_mismo_id():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    m.archivo.visibility = AttachmentVisibility.SHARED
    m.archivo.workspace_id = None
    m.archivo.uploader_user_id = None
    await _agregar_extraccion(
        m,
        archivo=m.archivo,
        anexo=m.anexo_pdf,
        data=EXTRACCION_VALIDA,
        reloj=reloj,
    )

    caso = _crear_caso_uso(m, reloj)
    d1 = await caso.execute(m.tender.id, workspace_id=None)
    d2 = await caso.execute(m.tender.id, workspace_id=None)

    assert d1 is not None and d2 is not None
    assert d1.id == d2.id
    assert d1.version == d2.version


@pytest.mark.asyncio
async def test_nueva_fuente_da_version_2():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    m.archivo.visibility = AttachmentVisibility.SHARED
    m.archivo.workspace_id = None
    m.archivo.uploader_user_id = None
    await _agregar_extraccion(
        m,
        archivo=m.archivo,
        anexo=m.anexo_pdf,
        data=EXTRACCION_VALIDA,
        reloj=reloj,
    )

    caso = _crear_caso_uso(m, reloj)
    d1 = await caso.execute(m.tender.id, workspace_id=None)
    assert d1 is not None and d1.version == 1

    # Agregar segundo archivo compartido
    archivo_2 = AttachmentFile(
        id=uuid4(),
        tender_attachment_id=m.anexo_docx.id,
        tender_id=m.tender.id,
        sha256="c" * 64,
        size_bytes=200,
        storage_key="k2",
        source=AttachmentFileSource.MANUAL,
        uploader_user_id=None,
        workspace_id=None,
        visibility=AttachmentVisibility.SHARED,
        trust=AttachmentTrust.CORROBORATED,
        status=AttachmentFileStatus.STORED,
        created_at=AHORA,
    )
    m.files.filas[archivo_2.id] = archivo_2
    await _agregar_extraccion(
        m,
        archivo=archivo_2,
        anexo=m.anexo_docx,
        data=EXTRACCION_VALIDA,
        reloj=reloj,
    )

    d2 = await caso.execute(m.tender.id, workspace_id=None)
    assert d2 is not None
    assert d2.version == 2
    assert d2.source_count == 2
    assert m.digests.filas[d1.id].is_current is False


@pytest.mark.asyncio
async def test_mover_closing_at_en_tender_da_version_2():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    m.archivo.visibility = AttachmentVisibility.SHARED
    m.archivo.workspace_id = None
    m.archivo.uploader_user_id = None
    await _agregar_extraccion(
        m,
        archivo=m.archivo,
        anexo=m.anexo_pdf,
        data=EXTRACCION_VALIDA,
        reloj=reloj,
    )

    caso = _crear_caso_uso(m, reloj)
    d1 = await caso.execute(m.tender.id, workspace_id=None)
    assert d1 is not None and d1.version == 1

    # Mover closing_at en el tender
    m.tender.first_call_closing_at = m.tender.first_call_closing_at + timedelta(
        days=1
    )
    m.tender.closing_at = m.tender.closing_at + timedelta(days=1)

    d2 = await caso.execute(m.tender.id, workspace_id=None)
    assert d2 is not None
    assert d2.version == 2
    assert m.digests.filas[d1.id].is_current is False


@pytest.mark.asyncio
async def test_borrar_todas_las_fuentes_de_compartido_da_version_vacia():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    m.archivo.visibility = AttachmentVisibility.SHARED
    m.archivo.workspace_id = None
    m.archivo.uploader_user_id = None
    await _agregar_extraccion(
        m,
        archivo=m.archivo,
        anexo=m.anexo_pdf,
        data=EXTRACCION_VALIDA,
        reloj=reloj,
    )

    caso = _crear_caso_uso(m, reloj)
    d1 = await caso.execute(m.tender.id, workspace_id=None)
    assert d1 is not None and d1.version == 1

    # Borrar las fuentes (quitar el archivo)
    m.files.filas.clear()

    d2 = await caso.execute(m.tender.id, workspace_id=None)
    assert d2 is not None
    assert d2.version == 2
    assert d2.source_count == 0


@pytest.mark.asyncio
async def test_sin_fuentes_y_sin_vigente_da_none():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    m.files.filas.clear()

    caso = _crear_caso_uso(m, reloj)
    digest = await caso.execute(m.tender.id, workspace_id=None)

    assert digest is None
    assert len(m.digests.filas) == 0


@pytest.mark.asyncio
async def test_empresa_sin_privados_retira_current():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    # El archivo es privado de WS_A
    await _agregar_extraccion(
        m,
        archivo=m.archivo,
        anexo=m.anexo_pdf,
        data=EXTRACCION_VALIDA,
        reloj=reloj,
    )

    caso = _crear_caso_uso(m, reloj)
    d_a = await caso.execute(m.tender.id, workspace_id=m.ws_a)
    assert d_a is not None and d_a.workspace_id == m.ws_a

    # Ahora WS_A borra su privado (m.files vacío)
    m.files.filas.clear()

    res = await caso.execute(m.tender.id, workspace_id=m.ws_a)
    assert res is None
    assert m.digests.filas[d_a.id].is_current is False


@pytest.mark.asyncio
async def test_privacidad_lanza_fuente_no_visible():
    m = mundo(AHORA)
    reloj = Reloj(AHORA)
    caso = _crear_caso_uso(m, reloj)

    # Simular una fuente privada de WS_A que intenta consolidarse con alcance None
    fuente_privada = FuenteDeExtraccion(
        extraction_id=uuid4(),
        attachment_file_id=m.archivo.id,
        tender_attachment_id=m.anexo_pdf.id,
        mp_document_id=1931003,
        documento="Bases.pdf",
        sha256=m.archivo.sha256,
        visibility=AttachmentVisibility.PRIVATE,
        trust=AttachmentTrust.PENDING,
        workspace_id=m.ws_a,
        data=AttachmentExtractionData.model_validate(EXTRACCION_VALIDA),
        citas_total=1,
        citas_verificadas=1,
        texto_disponible=True,
        model="test",
        prompt_version="anexos-v1",
        created_at=AHORA,
    )

    with pytest.raises(FuenteNoVisible):
        await caso.build_from(m.tender, None, [fuente_privada])
