"""Tests de consolidación determinista del resumen de licitación (plan 233, decisión 4)."""

from datetime import date, datetime
from uuid import UUID, uuid4

import pytest

from app.domain.entities.attachment_extraction import (
    AttachmentExtractionData,
    Cita,
    FechaExtraida,
    FuenteDeExtraccion,
    ItemExtraido,
    Presupuesto,
    Requisito,
    ResumenGeneral,
)
from app.domain.entities.attachment_file import (
    AttachmentTrust,
    AttachmentVisibility,
)
from app.domain.entities.tender import Tender
from app.domain.entities.tender_digest import (
    Discrepancia,
    TenderDigestData,
    TipoDeDiscrepancia,
)
from app.domain.errors.attachment_processing_errors import FuenteNoVisible
from app.domain.services.digest_consolidation import (
    alcance_para,
    consolidar,
    deduplicar_fuentes,
    exigir_privacidad,
    foto_de_la_api,
    huella_del_conjunto,
)

WS_A = uuid4()
WS_B = uuid4()
TENDER_ID = uuid4()

TENDER = Tender(
    id=TENDER_ID,
    code="1057539-228-COT26",
    name="Reparación de techumbre",
    status_id=1,
    status_code="publicada",
    published_at=datetime(2026, 9, 28, 13, 0),
    closing_at=datetime(2026, 10, 4, 18, 0),
    call_number=1,
    first_call_closing_at=datetime(2026, 10, 4, 18, 0),
    second_call_closing_at=datetime(2026, 10, 8, 18, 0),
    last_change_at=datetime(2026, 10, 1, 10, 0),
    buyer_rut="1-9",
    buyer_unit="U",
    available_amount_clp=5_000_000,
)


def _fuente(
    documento: str,
    data: AttachmentExtractionData,
    *,
    visibility: AttachmentVisibility = AttachmentVisibility.SHARED,
    workspace_id: UUID | None = None,
    attachment_id: UUID | None = None,
    file_id: UUID | None = None,
    sha256: str = "a" * 64,
    mp_document_id: int = 1,
) -> FuenteDeExtraccion:
    return FuenteDeExtraccion(
        extraction_id=uuid4(),
        attachment_file_id=file_id or uuid4(),
        tender_attachment_id=attachment_id or uuid4(),
        mp_document_id=mp_document_id,
        documento=documento,
        sha256=sha256,
        visibility=visibility,
        trust=AttachmentTrust.CORROBORATED,
        workspace_id=workspace_id,
        data=data,
        citas_total=len(list(data.todas_las_citas())),
        citas_verificadas=len(list(data.todas_las_citas())),
        texto_disponible=True,
        model="gemini-test",
        prompt_version="anexos-v1",
        created_at=datetime(2026, 10, 3, 12, 0),
    )


def test_cierre_del_anexo_distinto_al_de_la_api():
    cita = Cita(documento="Bases.pdf", pagina_u_hoja="1", cita="Cierre 05-10-2026 15:00", verificada=True)
    data = AttachmentExtractionData(
        fecha_cierre_primer_llamado=FechaExtraida(
            fecha=date(2026, 10, 5), hora="15:00", citas=[cita]
        ),
        resumen_general=ResumenGeneral(texto="Resumen", citas=[cita]),
    )
    f = _fuente("Bases.pdf", data)
    res = consolidar([f], TENDER)

    assert len(res.discrepancias) == 1
    d = res.discrepancias[0]
    assert d.tipo == TipoDeDiscrepancia.ANEXO_VS_API
    assert d.campo == "fecha_cierre_primer_llamado"
    assert d.tema == "Cierre del primer llamado"
    assert d.campo_api == "first_call_closing_at"
    assert d.valor_api == "04-10-2026 15:00"
    assert d.valores_anexos == ["05-10-2026 15:00"]
    assert d.descripcion == (
        "Mercado Público informa 04-10-2026 15:00 como cierre del primer llamado, "
        "pero «Bases.pdf» dice 05-10-2026 15:00."
    )


def test_segundo_llamado_distinto():
    cita = Cita(documento="Bases.pdf", pagina_u_hoja="1", cita="Cierre 2: 09-10-2026", verificada=True)
    data = AttachmentExtractionData(
        fecha_cierre_segundo_llamado=FechaExtraida(
            fecha=date(2026, 10, 9), hora=None, citas=[cita]
        ),
        resumen_general=ResumenGeneral(texto="Resumen", citas=[cita]),
    )
    f = _fuente("Bases.pdf", data)
    res = consolidar([f], TENDER)

    assert len(res.discrepancias) == 1
    d = res.discrepancias[0]
    assert d.campo_api == "second_call_closing_at"
    assert d.valor_api == "08-10-2026 15:00"
    assert d.valores_anexos == ["09-10-2026"]


def test_misma_fecha_sin_hora_no_es_discrepancia():
    cita = Cita(documento="Bases.pdf", cita="04-10-2026", verificada=True)
    data_sin_hora = AttachmentExtractionData(
        fecha_cierre_primer_llamado=FechaExtraida(
            fecha=date(2026, 10, 4), hora=None, citas=[cita]
        ),
        resumen_general=ResumenGeneral(texto="Resumen", citas=[cita]),
    )
    f1 = _fuente("Bases.pdf", data_sin_hora)
    res1 = consolidar([f1], TENDER)
    assert len(res1.discrepancias) == 0

    data_con_otra_hora = AttachmentExtractionData(
        fecha_cierre_primer_llamado=FechaExtraida(
            fecha=date(2026, 10, 4), hora="16:00", citas=[cita]
        ),
        resumen_general=ResumenGeneral(texto="Resumen", citas=[cita]),
    )
    f2 = _fuente("Bases.pdf", data_con_otra_hora)
    res2 = consolidar([f2], TENDER)
    assert len(res2.discrepancias) == 1


def test_sin_columna_del_llamado_compara_contra_closing_at():
    t_sin_primer = TENDER.model_copy(update={"first_call_closing_at": None, "call_number": None})
    cita = Cita(documento="Bases.pdf", cita="05-10-2026 15:00", verificada=True)
    data = AttachmentExtractionData(
        fecha_cierre_primer_llamado=FechaExtraida(
            fecha=date(2026, 10, 5), hora="15:00", citas=[cita]
        ),
        resumen_general=ResumenGeneral(texto="Resumen", citas=[cita]),
    )
    f = _fuente("Bases.pdf", data)
    res = consolidar([f], t_sin_primer)
    assert res.discrepancias[0].campo_api == "closing_at"

    t_segundo = TENDER.model_copy(update={"second_call_closing_at": None, "call_number": 2})
    data2 = AttachmentExtractionData(
        fecha_cierre_segundo_llamado=FechaExtraida(
            fecha=date(2026, 10, 9), hora="15:00", citas=[cita]
        ),
        resumen_general=ResumenGeneral(texto="Resumen", citas=[cita]),
    )
    f2 = _fuente("Bases.pdf", data2)
    res2 = consolidar([f2], t_segundo)
    assert res2.discrepancias[0].campo_api == "closing_at"


def test_presupuesto():
    cita = Cita(documento="Bases.pdf", cita="Monto $5.950.000", verificada=True)
    data = AttachmentExtractionData(
        presupuesto=Presupuesto(
            monto_clp=5_950_000,
            incluye_iva=True,
            monto_texto="$5.950.000",
            citas=[cita],
        ),
        resumen_general=ResumenGeneral(texto="Resumen", citas=[cita]),
    )
    f = _fuente("Bases.pdf", data)
    res = consolidar([f], TENDER)
    assert len(res.discrepancias) == 1
    d = res.discrepancias[0]
    assert d.campo_api == "available_amount_clp"
    assert d.valor_api == "$5.000.000"
    assert d.valores_anexos == ["$5.950.000"]
    assert d.descripcion == "Mercado Público informa $5.000.000 como presupuesto, pero «Bases.pdf» dice $5.950.000."

    # Diferencia menor a 1 peso no cuenta
    data_menor = AttachmentExtractionData(
        presupuesto=Presupuesto(
            monto_clp=5_000_000.4,
            incluye_iva=True,
            monto_texto="$5.000.000",
            citas=[cita],
        ),
        resumen_general=ResumenGeneral(texto="Resumen", citas=[cita]),
    )
    res_menor = consolidar([_fuente("Bases.pdf", data_menor)], TENDER)
    assert len(res_menor.discrepancias) == 0

    # Sin monto_clp numérico no se compara
    data_sin_num = AttachmentExtractionData(
        presupuesto=Presupuesto(
            monto_clp=None,
            monto_texto="100 UF",
            citas=[cita],
        ),
        resumen_general=ResumenGeneral(texto="Resumen", citas=[cita]),
    )
    res_sin_num = consolidar([_fuente("Bases.pdf", data_sin_num)], TENDER)
    assert len(res_sin_num.discrepancias) == 0


def test_publicacion_compara_solo_la_fecha():
    cita = Cita(documento="Bases.pdf", cita="28-09-2026", verificada=True)
    # Published_at en TENDER es 2026-09-28 13:00 UTC (10:00 Chile). Misma fecha -> no hay discrepancia
    data = AttachmentExtractionData(
        fecha_publicacion=FechaExtraida(fecha=date(2026, 9, 28), hora="08:00", citas=[cita]),
        resumen_general=ResumenGeneral(texto="Resumen", citas=[cita]),
    )
    res = consolidar([_fuente("Bases.pdf", data)], TENDER)
    assert len(res.discrepancias) == 0


def test_anexos_en_conflicto_dan_una_sola_discrepancia():
    c1 = Cita(documento="Bases.pdf", cita="05-10-2026 15:00", verificada=True)
    c2 = Cita(documento="Anexo 2.pdf", cita="06-10-2026 15:00", verificada=True)
    d1 = AttachmentExtractionData(
        fecha_cierre_primer_llamado=FechaExtraida(fecha=date(2026, 10, 5), hora="15:00", citas=[c1]),
        resumen_general=ResumenGeneral(texto="Resumen", citas=[c1]),
    )
    d2 = AttachmentExtractionData(
        fecha_cierre_primer_llamado=FechaExtraida(fecha=date(2026, 10, 6), hora="15:00", citas=[c2]),
        resumen_general=ResumenGeneral(texto="Resumen", citas=[c2]),
    )
    f1 = _fuente("Bases.pdf", d1, mp_document_id=1)
    f2 = _fuente("Anexo 2.pdf", d2, mp_document_id=2)
    res = consolidar([f1, f2], TENDER)

    assert res.campos.fecha_cierre_primer_llamado.en_conflicto is True
    assert res.campos.fecha_cierre_primer_llamado.valor is None
    assert len(res.campos.fecha_cierre_primer_llamado.alternativas) == 2

    assert len(res.discrepancias) == 1
    disc = res.discrepancias[0]
    assert disc.tipo == TipoDeDiscrepancia.ANEXO_VS_ANEXO
    assert disc.valor_api == "04-10-2026 15:00"
    assert disc.descripcion == (
        "Los anexos no coinciden en cierre del primer llamado: «Bases.pdf» dice 05-10-2026 15:00; "
        "«Anexo 2.pdf» dice 06-10-2026 15:00. Mercado Público informa 04-10-2026 15:00."
    )


def test_fecha_sin_hora_se_funde_con_la_que_trae_hora():
    c1 = Cita(documento="Bases.pdf", cita="05-10-2026", verificada=True)
    c2 = Cita(documento="Anexo 2.pdf", cita="05-10-2026 15:00", verificada=True)
    d1 = AttachmentExtractionData(
        fecha_cierre_primer_llamado=FechaExtraida(fecha=date(2026, 10, 5), hora=None, citas=[c1]),
        resumen_general=ResumenGeneral(texto="Resumen", citas=[c1]),
    )
    d2 = AttachmentExtractionData(
        fecha_cierre_primer_llamado=FechaExtraida(fecha=date(2026, 10, 5), hora="15:00", citas=[c2]),
        resumen_general=ResumenGeneral(texto="Resumen", citas=[c2]),
    )
    f1 = _fuente("Bases.pdf", d1, mp_document_id=1)
    f2 = _fuente("Anexo 2.pdf", d2, mp_document_id=2)
    res = consolidar([f1, f2], TENDER)

    assert res.campos.fecha_cierre_primer_llamado.en_conflicto is False
    assert res.campos.fecha_cierre_primer_llamado.valor.hora == "15:00"
    assert len(res.campos.fecha_cierre_primer_llamado.citas) == 2


def test_requisitos_duplicados_se_funden():
    c1 = Cita(documento="Bases.pdf", cita="Cita 1", verificada=True)
    c2 = Cita(documento="Anexo 2.pdf", cita="Cita 2", verificada=True)
    r1 = Requisito(
        descripcion="Inscripción vigente del proyectista en el Registro de Consultores ESVAL",
        tipo="tecnico",
        obligatorio=False,
        citas=[c1],
    )
    r2 = Requisito(
        descripcion="Inscripción Vigente del Proyectista en Registro de Consultores ESVAL.",
        tipo="tecnico",
        obligatorio=True,
        citas=[c2],
    )
    r3 = Requisito(descripcion="Boleta de garantía bancaria", tipo="economico", citas=[c1])
    d1 = AttachmentExtractionData(requisitos=[r1, r3], resumen_general=ResumenGeneral(texto="x", citas=[c1]))
    d2 = AttachmentExtractionData(requisitos=[r2], resumen_general=ResumenGeneral(texto="x", citas=[c2]))

    f1 = _fuente("Bases.pdf", d1, mp_document_id=1)
    f2 = _fuente("Anexo 2.pdf", d2, mp_document_id=2)
    res = consolidar([f1, f2], TENDER)

    assert len(res.requisitos) == 2
    req_fundido = next(r for r in res.requisitos if "ESVAL" in r.descripcion)
    assert req_fundido.obligatorio is True
    assert len(req_fundido.citas) == 2


def test_items_con_distinta_cantidad_no_se_funden():
    c = Cita(documento="Bases.pdf", cita="c", verificada=True)
    i1 = ItemExtraido(descripcion="Pintura esmalte", cantidad=10, unidad="gl", citas=[c])
    i2 = ItemExtraido(descripcion="Pintura esmalte", cantidad=20, unidad="gl", citas=[c])
    d = AttachmentExtractionData(items=[i1, i2], resumen_general=ResumenGeneral(texto="x", citas=[c]))
    res = consolidar([_fuente("Bases.pdf", d)], TENDER)
    assert len(res.items) == 2


def test_un_resumen_por_anexo_en_orden_estable():
    c = Cita(documento="Doc", cita="c", verificada=True)
    d = AttachmentExtractionData(resumen_general=ResumenGeneral(texto="T", citas=[c]))
    f1 = _fuente("Zeta.pdf", d, mp_document_id=2)
    f2 = _fuente("Alfa.pdf", d, mp_document_id=1)
    res = consolidar([f1, f2], TENDER)
    assert [r.documento for r in res.resumenes] == ["Alfa.pdf", "Zeta.pdf"]


def test_fuentes_duplicadas_por_contenido():
    att_id = uuid4()
    c = Cita(documento="Bases.pdf", cita="c", verificada=True)
    d = AttachmentExtractionData(resumen_general=ResumenGeneral(texto="T", citas=[c]))
    f_shared = _fuente("Bases.pdf", d, attachment_id=att_id, sha256="abc", visibility=AttachmentVisibility.SHARED)
    f_private = _fuente("Bases.pdf", d, attachment_id=att_id, sha256="abc", visibility=AttachmentVisibility.PRIVATE, workspace_id=WS_A)

    fuentes_dedup = deduplicar_fuentes([f_private, f_shared])
    assert len(fuentes_dedup) == 1
    assert fuentes_dedup[0].visibility == AttachmentVisibility.SHARED


def test_huella_cambia_con_visibilidad_y_version_del_algoritmo():
    c = Cita(documento="Bases.pdf", cita="c", verificada=True)
    d = AttachmentExtractionData(resumen_general=ResumenGeneral(texto="T", citas=[c]))
    f1 = _fuente("A.pdf", d, visibility=AttachmentVisibility.SHARED)
    f2 = _fuente("B.pdf", d, visibility=AttachmentVisibility.PRIVATE, workspace_id=WS_A)

    h1 = huella_del_conjunto([f1, f2])
    h2 = huella_del_conjunto([f2, f1])
    assert h1 == h2

    f2_mod = _fuente("B.pdf", d, visibility=AttachmentVisibility.SHARED)
    h3 = huella_del_conjunto([f1, f2_mod])
    assert h1 != h3


def test_foto_de_la_api():
    foto = foto_de_la_api(TENDER)
    assert foto == {
        "available_amount_clp": 5000000.0,
        "published_at": "2026-09-28T13:00:00Z",
        "closing_at": "2026-10-04T18:00:00Z",
        "first_call_closing_at": "2026-10-04T18:00:00Z",
        "second_call_closing_at": "2026-10-08T18:00:00Z",
        "call_number": 1,
    }


def test_privacidad_alcance_y_guarda():
    c = Cita(documento="Bases.pdf", cita="c", verificada=True)
    d = AttachmentExtractionData(resumen_general=ResumenGeneral(texto="T", citas=[c]))
    f_shared = _fuente("Bases.pdf", d, visibility=AttachmentVisibility.SHARED)
    f_priv_a = _fuente("PrivA.pdf", d, visibility=AttachmentVisibility.PRIVATE, workspace_id=WS_A)

    assert alcance_para([f_priv_a, f_shared], WS_A) == WS_A
    assert alcance_para([f_priv_a, f_shared], WS_B) is None
    assert alcance_para([f_priv_a, f_shared], None) is None

    with pytest.raises(FuenteNoVisible):
        exigir_privacidad([f_priv_a], None)

    with pytest.raises(FuenteNoVisible):
        exigir_privacidad([f_priv_a], WS_B)

    # Con su propio workspace no lanza
    exigir_privacidad([f_shared, f_priv_a], WS_A)


def test_sin_fuentes():
    res = consolidar([], TENDER)
    assert res == TenderDigestData.vacio()
