"""Tests de lectura y formateo de hojas Excel XLSX (plan 233, decisión 4)."""

from app.infrastructure.services.document_text import (
    formatear_hojas,
    xlsx_hojas,
    xlsx_to_text,
)
from tests.unit.infrastructure.attachment_documents import xlsx


def test_xlsx_to_text_y_xlsx_hojas():
    datos = xlsx({"Hoja1": [["a", 1], [None, "b"]]})
    hojas = xlsx_hojas(datos, read_only=True)
    assert len(hojas) == 1
    assert hojas[0][0] == "Hoja1"
    assert hojas[0][1] == ["a | 1", " | b"]

    texto = xlsx_to_text(datos, "x.xlsx")
    assert texto == "=== DOCUMENTO EXCEL: x.xlsx ===\n\n--- Hoja: Hoja1 ---\na | 1\n | b"


def test_xlsx_to_text_con_error():
    texto = xlsx_to_text(b"basura", "archivo.xlsx")
    assert texto == "[Documento Excel adjunto: archivo.xlsx (no se pudo parsear el contenido tabular)]"
