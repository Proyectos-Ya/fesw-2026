"""Tests de inspección OOXML y extracción de texto de docx (plan 233, decisión 4)."""

import zipfile
from io import BytesIO

from app.domain.entities.attachment_processing import MotivoDeEstado
from app.domain.services.attachment_file_signatures import FormatoLegible
from app.infrastructure.services.attachments.ooxml import (
    LimitesZip,
    docx_a_texto,
    inspeccionar_ooxml,
)
from tests.unit.infrastructure.attachment_documents import docx, xlsx, zip_bomba


def test_docx_valido():
    datos = docx(["Hola mundo"])
    assert inspeccionar_ooxml(datos, FormatoLegible.DOCX) is None


def test_macros_detectadas():
    con_vba = docx(["Hola"], extra={"word/vbaProject.bin": b"macro"})
    assert inspeccionar_ooxml(con_vba, FormatoLegible.DOCX) == MotivoDeEstado.MACRO_ENABLED

    con_tipo_macro = docx(
        ["Hola"],
        content_types_extra='<Override PartName="/word/document.xml" ContentType="application/vnd.ms-word.document.macroEnabled.main+xml"/>',
    )
    assert inspeccionar_ooxml(con_tipo_macro, FormatoLegible.DOCX) == MotivoDeEstado.MACRO_ENABLED


def test_zip_bomba_rechazada():
    bomba = zip_bomba()
    assert inspeccionar_ooxml(bomba, FormatoLegible.DOCX) == MotivoDeEstado.ARCHIVE_TOO_LARGE


def test_limites_zip_personalizados():
    # max_total_bytes
    limites_bytes = LimitesZip(max_total_bytes=1024)
    dos_entradas = docx(["x"], extra={"word/extra.bin": b"a" * 1024})
    assert inspeccionar_ooxml(dos_entradas, FormatoLegible.DOCX, limites_bytes) == MotivoDeEstado.ARCHIVE_TOO_LARGE

    # max_entradas
    limites_entradas = LimitesZip(max_entradas=10)
    muchas_entradas = docx(["x"], extra={f"word/extra_{i}.bin": b"a" for i in range(10)})
    assert inspeccionar_ooxml(muchas_entradas, FormatoLegible.DOCX, limites_entradas) == MotivoDeEstado.ARCHIVE_TOO_LARGE


def test_compresion_no_permitida_o_corrupta():
    bio = BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_BZIP2) as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<doc/>")
    assert inspeccionar_ooxml(bio.getvalue(), FormatoLegible.DOCX) == MotivoDeEstado.CONTENT_MISMATCH


def test_sin_parte_principal_o_no_es_zip():
    bio = BytesIO()
    with zipfile.ZipFile(bio, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
    assert inspeccionar_ooxml(bio.getvalue(), FormatoLegible.DOCX) == MotivoDeEstado.CONTENT_MISMATCH

    assert inspeccionar_ooxml(b"no es zip", FormatoLegible.DOCX) == MotivoDeEstado.CONTENT_MISMATCH


def test_xml_con_doctype_o_entity_rechazado():
    con_doctype = docx(
        ["x"],
        extra={"word/document.xml": b'<?xml version="1.0"?><!DOCTYPE doc SYSTEM "x"><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body/></w:document>'},
    )
    assert inspeccionar_ooxml(con_doctype, FormatoLegible.DOCX) == MotivoDeEstado.CONTENT_MISMATCH


def test_xlsx_valido():
    datos = xlsx({"Hoja1": [["A", "B"], [1, 2]]})
    assert inspeccionar_ooxml(datos, FormatoLegible.XLSX) is None


def test_docx_a_texto_detallado():
    # Párrafo con dos runs, tab y break
    bio = BytesIO()
    with zipfile.ZipFile(bio, "w") as zf:
        zf.writestr(
            "word/document.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body>
                <w:p>
                    <w:r><w:t>Plazo: </w:t></w:r>
                    <w:r><w:tab/><w:t>80 días</w:t></w:r>
                    <w:r><w:br/><w:t>corridos</w:t></w:r>
                </w:p>
                <w:tbl>
                    <w:tr>
                        <w:tc><w:p><w:r><w:t>a</w:t></w:r></w:p></w:tc>
                        <w:tc><w:p><w:r><w:t>b</w:t></w:r></w:p></w:tc>
                    </w:tr>
                    <w:tr>
                        <w:tc><w:p><w:r><w:t>c</w:t></w:r></w:p></w:tc>
                        <w:tc><w:p><w:r><w:t>d</w:t></w:r></w:p></w:tc>
                    </w:tr>
                </w:tbl>
                <w:p>
                    <w:r><w:delText>borrado</w:delText></w:r>
                </w:p>
                <w:sdt>
                    <w:sdtContent>
                        <w:p><w:r><w:t>Contenido estructurado</w:t></w:r></w:p>
                    </w:sdtContent>
                </w:sdt>
            </w:body>
            </w:document>
            """,
        )
    texto = docx_a_texto(bio.getvalue())
    assert "Plazo: \t80 días\ncorridos" in texto
    assert "a | b" in texto
    assert "c | d" in texto
    assert "borrado" not in texto
    assert "Contenido estructurado" in texto
