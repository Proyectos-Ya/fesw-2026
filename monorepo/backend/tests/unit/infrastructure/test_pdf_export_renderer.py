from io import BytesIO

from pypdf import PdfReader

from app.infrastructure.services.exports.pdf_renderer import ReportLabPdfRenderer
from tests.unit.infrastructure.export_samples import snapshot


def _texto(contenido: bytes) -> str:
    lector = PdfReader(BytesIO(contenido))
    return "\n".join(pagina.extract_text() for pagina in lector.pages)


def _paginas(contenido: bytes) -> int:
    return len(PdfReader(BytesIO(contenido)).pages)


def test_es_un_pdf_valido():
    contenido = ReportLabPdfRenderer().render(snapshot())

    assert contenido.startswith(b"%PDF")
    assert _paginas(contenido) >= 1


def test_incluye_los_datos_de_la_licitacion_con_tildes_y_enes():
    texto = _texto(ReportLabPdfRenderer().render(snapshot()))

    assert "Mantención de áreas verdes Ñuñoa" in texto
    assert "1057539-228-COT26" in texto
    assert "Municipalidad de Ñuñoa" in texto
    assert "$5.000.000" in texto


def test_incluye_el_analisis_y_la_justificacion():
    # Criterio 3.
    texto = _texto(ReportLabPdfRenderer().render(snapshot()))

    assert "84%" in texto
    assert "Postular" in texto
    assert "experiencia declarada en mantención" in texto


def test_incluye_la_cotizacion_de_la_empresa_con_su_total():
    # Criterio 3: las cotizaciones asociadas a la licitación y a la empresa.
    texto = _texto(ReportLabPdfRenderer().render(snapshot()))

    assert "Constructora Andes" in texto
    assert "Fertilizante" in texto
    assert "$32.475" in texto
    assert "$47.475" in texto


def test_sin_analisis_ni_cotizacion_lo_dice_en_vez_de_omitirlo():
    texto = _texto(
        ReportLabPdfRenderer().render(snapshot(analysis=None, score_pct=None, quotation=None))
    )

    assert "Sin análisis de compatibilidad" in texto
    assert "Sin cotización registrada" in texto


def test_incluye_las_fechas_clave_en_hora_de_chile():
    texto = _texto(ReportLabPdfRenderer().render(snapshot()))

    # 18:00 UTC del 8-oct = 15:00 en Chile.
    assert "08-10-2026 15:00" in texto


def test_cada_pagina_lleva_numero_y_fecha_de_generacion():
    texto = _texto(ReportLabPdfRenderer().render(snapshot()))

    assert "Página 1 de" in texto
    assert "Generado el 28-09-2026 12:00" in texto


def test_una_justificacion_larga_pasa_a_otra_pagina_sin_perderse():
    larga = "Párrafo de justificación con bastante detalle. " * 400
    base = snapshot()
    analisis = base.analysis.model_copy(update={"justification": larga + "FIN-DEL-TEXTO"})

    contenido = ReportLabPdfRenderer().render(snapshot(analysis=analisis))

    assert _paginas(contenido) > 1
    assert "FIN-DEL-TEXTO" in _texto(contenido)
    assert f"Página {_paginas(contenido)} de {_paginas(contenido)}" in _texto(contenido)


def test_un_texto_con_marcado_no_rompe_el_pdf():
    # ReportLab interpreta etiquetas en los párrafos; un "<" de las bases no
    # debe tumbar la generación ni inyectar formato.
    base = snapshot()
    analisis = base.analysis.model_copy(
        update={"justification": "Monto < $1.000 & plazo > 5 días <b>sin cerrar"}
    )

    texto = _texto(ReportLabPdfRenderer().render(snapshot(analysis=analisis)))

    assert "Monto < $1.000 & plazo > 5 días <b>sin cerrar" in texto
