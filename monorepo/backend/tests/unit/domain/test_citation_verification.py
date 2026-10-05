"""Tests de verificación determinista y aproximada de citas (plan 233, decisión 4)."""

from pypdf import PdfReader

from app.domain.entities.attachment_extraction import AttachmentExtractionData
from app.domain.services.citation_verification import (
    IndiceDeTexto,
    normalizar_para_citas,
    verificar_cita,
    verificar_extraccion,
)
from tests.unit.application.attachment_processing_fakes import (
    EXTRACCION_VALIDA,
    PDF_PATH,
)


def _crear_indice_fixture() -> IndiceDeTexto:
    lector = PdfReader(PDF_PATH)
    secciones = [pagina.extract_text() or "" for pagina in lector.pages]
    return IndiceDeTexto.desde_secciones(secciones)


def test_normalizar_para_citas():
    texto = "Contra-\ntista ÑANDÚ ﬁnal"
    assert normalizar_para_citas(texto) == "contratista nandu final"


def test_casos_de_citas_en_fixture_pdf():
    indice = _crear_indice_fixture()

    # Cruza un salto de línea
    c1 = (
        "Los siguientes Términos Técnicos de Referencia son de carácter general y"
        " se refieren a la contratación de la confección de los diseños"
    )
    assert verificar_cita(c1, indice) is True

    # La misma sin "Técnicos" (cobertura difusa sobre 4 tokens)
    c2 = (
        "Los siguientes Términos de Referencia son de carácter general y"
        " se refieren a la contratación de la confección de los diseños"
    )
    assert verificar_cita(c2, indice) is True

    # Cita exacta presente
    c3 = (
        "El contrato es uno a modalidad suma alzada, cuyo monto total del será"
        " de $X.XXX.XXX, impuestos incluidos."
    )
    assert verificar_cita(c3, indice) is True

    # Paráfrasis (cobertura baja ~0.67): debe fallar
    c4 = "El contrato es a suma alzada y su monto total incluye impuestos"
    assert verificar_cita(c4, indice) is False

    # Ausente completamente
    c5 = "La garantía de seriedad de la oferta corresponde al 5% del monto ofertado"
    assert verificar_cita(c5, indice) is False

    # 5 tokens, exacta
    c6 = "Memoria explicativa y de cálculos"
    assert verificar_cita(c6, indice) is True

    # 3 tokens, exacta
    c7 = "Plano del Proyecto"
    assert verificar_cita(c7, indice) is True

    # 3 tokens, no exacta: solo se acepta exacta si < 4 tokens
    c8 = "Plano de la obra"
    assert verificar_cita(c8, indice) is False

    # Con elipsis: ambos fragmentos existen
    c9 = "La Ilustre Municipalidad de Catemu requiere … conexión de agua potable"
    assert verificar_cita(c9, indice) is True

    # Con elipsis: segundo fragmento ausente
    c10 = "La Ilustre Municipalidad de Catemu requiere … una piscina olímpica"
    assert verificar_cita(c10, indice) is False


def test_casos_borde_indice_nulo_o_vacio():
    assert verificar_cita("Cita de prueba", None) is False
    vacio = IndiceDeTexto.desde_secciones([])
    assert verificar_cita("Cita de prueba", vacio) is False


def test_verificar_extraccion():
    indice = _crear_indice_fixture()
    data = AttachmentExtractionData.model_validate(EXTRACCION_VALIDA)
    verificada = verificar_extraccion(data, indice)

    # Cada cita tiene un booleano en 'verificada'
    for c in verificada.todas_las_citas():
        assert isinstance(c.verificada, bool)

    # El original no mutó (verificada sigue en None)
    for c in data.todas_las_citas():
        assert c.verificada is None

    # Con índice None, todas quedan en False
    todas_falsas = verificar_extraccion(data, None)
    assert all(c.verificada is False for c in todas_falsas.todas_las_citas())
