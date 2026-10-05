"""Constructores de documentos docx, xlsx y zip bombs para pruebas (plan 233, decisión 4)."""

import html
import zipfile
from io import BytesIO
from typing import Any

import openpyxl

PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    b"\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
)


def docx(
    parrafos: list[str],
    *,
    tablas: tuple[list[list[str]], ...] = (),
    extra: dict[str, bytes] | None = None,
    content_types_extra: str = "",
) -> bytes:
    bio = BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
            '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
            '  <Default Extension="xml" ContentType="application/xml"/>\n'
            '  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>\n'
            f"  {content_types_extra}\n"
            "</Types>"
        )
        zf.writestr("[Content_Types].xml", content_types)

        rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>\n'
            "</Relationships>"
        )
        zf.writestr("_rels/.rels", rels)

        if not (extra and "word/document.xml" in extra):
            doc_xml_parts = [
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n'
                "<w:body>"
            ]
            for p in parrafos:
                doc_xml_parts.append(
                    f"<w:p><w:r><w:t>{html.escape(p)}</w:t></w:r></w:p>"
                )
            for t in tablas:
                doc_xml_parts.append("<w:tbl>")
                for fila in t:
                    doc_xml_parts.append("<w:tr>")
                    for celda in fila:
                        doc_xml_parts.append(
                            f"<w:tc><w:p><w:r><w:t>{html.escape(celda)}</w:t></w:r></w:p></w:tc>"
                        )
                    doc_xml_parts.append("</w:tr>")
                doc_xml_parts.append("</w:tbl>")
            doc_xml_parts.append("</w:body></w:document>")
            zf.writestr("word/document.xml", "".join(doc_xml_parts))

        if extra:
            for k, v in extra.items():
                zf.writestr(k, v)
    return bio.getvalue()


def xlsx(hojas: dict[str, list[list[Any]]]) -> bytes:
    wb = openpyxl.Workbook()
    first = True
    for sheet_name, filas in hojas.items():
        if first:
            ws = wb.active
            ws.title = sheet_name
            first = False
        else:
            ws = wb.create_sheet(title=sheet_name)
        for fila in filas:
            ws.append(fila)
    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


def zip_bomba(
    nombre: str = "word/document.xml", tamano: int = 2 * 1024 * 1024
) -> bytes:
    bio = BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
            '  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>\n'
            "</Types>",
        )
        zf.writestr(nombre, b"\x00" * tamano)
    return bio.getvalue()
