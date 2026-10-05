"""Tests de StdlibAttachmentContentReader (plan 233, decisión 4)."""

import time

import pytest

from app.domain.entities.attachment_processing import MotivoDeEstado
from app.domain.services.attachment_file_signatures import (
    FormatoLegible,
    Veredicto,
)
from app.infrastructure.services.attachments.content_reader import (
    StdlibAttachmentContentReader,
)
from tests.unit.application.attachment_processing_fakes import PDF_BYTES
from tests.unit.infrastructure.attachment_documents import (
    PNG_1X1,
    docx,
    xlsx,
    zip_bomba,
)


@pytest.mark.asyncio
async def test_inspect_content_reader():
    reader = StdlibAttachmentContentReader()

    res_pdf = await reader.inspect(PDF_BYTES, "pdf")
    assert res_pdf.veredicto == Veredicto.OK
    assert res_pdf.formato == FormatoLegible.PDF

    res_bomba = await reader.inspect(zip_bomba(), "docx")
    assert res_bomba.veredicto == Veredicto.RECHAZADO
    assert res_bomba.motivo == MotivoDeEstado.ARCHIVE_TOO_LARGE

    res_macro = await reader.inspect(docx(["x"], extra={"word/vbaProject.bin": b"vba"}), "docx")
    assert res_macro.veredicto == Veredicto.RECHAZADO
    assert res_macro.motivo == MotivoDeEstado.MACRO_ENABLED

    res_docx = await reader.inspect(docx(["Texto válido"]), "docx")
    assert res_docx.veredicto == Veredicto.OK
    assert res_docx.mime == "text/plain"


@pytest.mark.asyncio
async def test_read_text_pdf():
    reader = StdlibAttachmentContentReader()
    res = await reader.read_text(PDF_BYTES, FormatoLegible.PDF, nombre="Bases.pdf")
    assert len(res.secciones) == 9
    assert res.secciones[0].etiqueta == "1"
    assert res.secciones[8].etiqueta == "9"
    assert res.disponible is True
    assert res.para_modelo is None
    assert res.paginas == 9


@pytest.mark.asyncio
async def test_read_text_imagen():
    reader = StdlibAttachmentContentReader()
    res = await reader.read_text(PNG_1X1, FormatoLegible.IMAGEN, nombre="Foto.png")
    assert res.secciones == ()
    assert res.disponible is False
    assert res.para_modelo is None


@pytest.mark.asyncio
async def test_read_text_docx():
    reader = StdlibAttachmentContentReader()
    datos = docx(["Párrafo de prueba con suficiente texto para estar disponible y verificable"])
    res = await reader.read_text(datos, FormatoLegible.DOCX, nombre="Doc.docx")
    assert len(res.secciones) == 1
    assert res.secciones[0].etiqueta == "documento"
    assert "Párrafo de prueba" in res.secciones[0].texto
    assert res.para_modelo == res.secciones[0].texto
    assert res.disponible is True


@pytest.mark.asyncio
async def test_read_text_xlsx():
    reader = StdlibAttachmentContentReader()
    datos = xlsx({"Hoja1": [["Item", "Precio"], ["A", 100]], "Hoja2": [["Obs", "Nota"]]})
    res = await reader.read_text(datos, FormatoLegible.XLSX, nombre="Anexo.xlsx")
    assert len(res.secciones) == 2
    assert res.secciones[0].etiqueta == "Hoja1"
    assert res.secciones[1].etiqueta == "Hoja2"
    assert res.para_modelo is not None
    assert "=== DOCUMENTO EXCEL: Anexo.xlsx ===" in res.para_modelo


@pytest.mark.asyncio
async def test_read_text_truncado():
    reader = StdlibAttachmentContentReader(max_caracteres=50)
    datos = docx(["Texto muy largo que excede los cincuenta caracteres configurados"])
    res = await reader.read_text(datos, FormatoLegible.DOCX, nombre="Largo.docx")
    assert res.para_modelo is not None
    assert res.para_modelo.endswith("\n[… documento truncado …]")


@pytest.mark.asyncio
async def test_read_text_timeout(monkeypatch):
    reader = StdlibAttachmentContentReader(timeout_seconds=0.01)

    def _dormir(*args, **kwargs):
        time.sleep(0.05)
        return "x"

    monkeypatch.setattr(reader, "_leer", _dormir)
    res = await reader.read_text(b"bytes", FormatoLegible.DOCX, nombre="Lento.docx")
    assert res.secciones == ()
