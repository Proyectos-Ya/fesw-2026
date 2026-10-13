from datetime import date, datetime
from uuid import uuid4

from app.application.use_cases.milestones.milestone_derivation import derivar_hitos_desde_digest
from app.domain.entities.attachment_extraction import (
    AttachmentExtractionData,
    Cita,
    FuenteDeExtraccion,
    ResumenGeneral,
)
from app.domain.entities.attachment_file import AttachmentTrust, AttachmentVisibility
from app.domain.entities.tender_digest import (
    CampoConsolidado,
    CamposConsolidados,
    CitaDeFuente,
    TenderDigestData,
    ValorDeFecha,
    ValorDeVisita,
)
from app.domain.entities.tender_milestone import MilestoneKind, MilestoneSource


def _crear_data(doc: str = "Bases.pdf") -> AttachmentExtractionData:
    return AttachmentExtractionData(
        resumen_general=ResumenGeneral(
            texto="Resumen",
            citas=[Cita(documento=doc, cita="Cita resumen", verificada=True)],
        )
    )


def _crear_cita(doc: str, archivo_id=None) -> CitaDeFuente:
    return CitaDeFuente(
        documento=doc,
        pagina_u_hoja="2",
        cita="Texto de cita relevante",
        verificada=True,
        anexo_id=uuid4(),
        archivo_id=archivo_id or uuid4(),
    )


def test_derivar_hitos_desde_digest_con_fechas():
    user_id = uuid4()
    tender_id = uuid4()
    archivo_id_bases = uuid4()

    fuente = FuenteDeExtraccion(
        extraction_id=uuid4(),
        attachment_file_id=archivo_id_bases,
        tender_attachment_id=uuid4(),
        mp_document_id=101,
        documento="Bases.pdf",
        sha256="abc",
        visibility=AttachmentVisibility.SHARED,
        trust=AttachmentTrust.CORROBORATED,
        workspace_id=None,
        data=_crear_data("Bases.pdf"),
        citas_total=5,
        citas_verificadas=5,
        texto_disponible=True,
        model="gemini-3.1-flash-lite",
        prompt_version="anexos-v1",
        created_at=datetime(2026, 10, 4),
    )

    cita_bases = _crear_cita("Bases.pdf", archivo_id=archivo_id_bases)

    digest = TenderDigestData.vacio()
    digest.campos = CamposConsolidados(
        fecha_publicacion=CampoConsolidado(
            valor=ValorDeFecha(fecha=date(2026, 10, 1), hora="10:00"),
            citas=[cita_bases],
        ),
        fecha_cierre_primer_llamado=CampoConsolidado(
            valor=ValorDeFecha(fecha=date(2026, 10, 15), hora="15:00"),
            citas=[cita_bases],
        ),
        visita_tecnica=CampoConsolidado(
            valor=ValorDeVisita(obligatoria=True, fecha=date(2026, 10, 8), hora="11:00", lugar="Av. Providencia 123"),
            citas=[cita_bases],
        ),
    )

    hitos = derivar_hitos_desde_digest(digest, [fuente], user_id, tender_id)
    assert len(hitos) == 3

    kinds = [h.kind for h in hitos]
    assert MilestoneKind.PUBLICACION in kinds
    assert MilestoneKind.CIERRE_POSTULACION in kinds
    assert MilestoneKind.VISITA_TECNICA in kinds

    for h in hitos:
        assert h.user_id == user_id
        assert h.tender_id == tender_id
        assert h.source == MilestoneSource.IA_DOCUMENTO
        assert h.source_file_id == archivo_id_bases
        assert h.has_time is True


def test_derivar_hitos_con_segundo_llamado():
    user_id = uuid4()
    tender_id = uuid4()
    archivo_id = uuid4()

    fuente = FuenteDeExtraccion(
        extraction_id=uuid4(),
        attachment_file_id=archivo_id,
        tender_attachment_id=uuid4(),
        mp_document_id=102,
        documento="Bases.pdf",
        sha256="abc",
        visibility=AttachmentVisibility.SHARED,
        trust=AttachmentTrust.CORROBORATED,
        workspace_id=None,
        data=_crear_data("Bases.pdf"),
        citas_total=1,
        citas_verificadas=1,
        texto_disponible=True,
        model="gemini-3.1-flash-lite",
        prompt_version="anexos-v1",
        created_at=datetime(2026, 10, 4),
    )

    digest = TenderDigestData.vacio()
    digest.campos = CamposConsolidados(
        fecha_cierre_segundo_llamado=CampoConsolidado(
            valor=ValorDeFecha(fecha=date(2026, 10, 20), hora="14:00"),
            citas=[_crear_cita("Bases.pdf", archivo_id=archivo_id)],
        )
    )

    hitos = derivar_hitos_desde_digest(digest, [fuente], user_id, tender_id)
    assert len(hitos) == 1
    assert hitos[0].kind == MilestoneKind.CIERRE_SEGUNDO_LLAMADO
    assert hitos[0].source_file_id == archivo_id


def test_licitacion_sin_extracciones_devuelve_vacio():
    user_id = uuid4()
    tender_id = uuid4()
    digest = TenderDigestData.vacio()

    hitos = derivar_hitos_desde_digest(digest, [], user_id, tender_id)
    assert hitos == []
