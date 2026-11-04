"""Tests de clasificación por firma de archivos (plan 233, decisión 4)."""

import pytest

from app.domain.entities.attachment_processing import MotivoDeEstado
from app.domain.services.attachment_file_signatures import (
    ArchivoInspeccionado,
    FormatoLegible,
    Veredicto,
    clasificar_por_firma,
)

_OLE2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 20
_WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 "


def test_pdf_valido():
    res = clasificar_por_firma(b"%PDF-1.7\n...", "pdf")
    assert res == ArchivoInspeccionado(Veredicto.OK, FormatoLegible.PDF, "application/pdf")

    # Con basura previa antes de 1024 bytes
    res_basura = clasificar_por_firma(b"\n\r garbage %PDF-1.4", "pdf")
    assert res_basura == ArchivoInspeccionado(Veredicto.OK, FormatoLegible.PDF, "application/pdf")


def test_pdf_invalido():
    res = clasificar_por_firma(b"PK\x03\x04...", "pdf")
    assert res == ArchivoInspeccionado(Veredicto.RECHAZADO, motivo=MotivoDeEstado.CONTENT_MISMATCH)

    res_exe = clasificar_por_firma(b"MZ\x90\x00", "pdf")
    assert res_exe == ArchivoInspeccionado(Veredicto.RECHAZADO, motivo=MotivoDeEstado.CONTENT_MISMATCH)


def test_imagenes():
    res_png = clasificar_por_firma(_PNG, "png")
    assert res_png == ArchivoInspeccionado(Veredicto.OK, FormatoLegible.IMAGEN, "image/png")

    # Firma PNG con extensión jpg (se detecta por mime)
    res_png_como_jpg = clasificar_por_firma(_PNG, "jpg")
    assert res_png_como_jpg == ArchivoInspeccionado(Veredicto.OK, FormatoLegible.IMAGEN, "image/png")

    res_webp = clasificar_por_firma(_WEBP, "webp")
    assert res_webp == ArchivoInspeccionado(Veredicto.OK, FormatoLegible.IMAGEN, "image/webp")

    # Extensión de imagen pero contenido no coincide
    res_falsa = clasificar_por_firma(b"GIF89a", "png")
    assert res_falsa == ArchivoInspeccionado(Veredicto.RECHAZADO, motivo=MotivoDeEstado.CONTENT_MISMATCH)


def test_office_moderno():
    res_docx = clasificar_por_firma(b"PK\x03\x04...", "docx")
    assert res_docx == ArchivoInspeccionado(Veredicto.OK, FormatoLegible.DOCX, mime=None)

    res_xlsx = clasificar_por_firma(b"PK\x03\x04...", "xlsx")
    assert res_xlsx == ArchivoInspeccionado(Veredicto.OK, FormatoLegible.XLSX, mime=None)

    # OLE2 en xlsx es cifrado o antiguo
    res_ole2_xlsx = clasificar_por_firma(_OLE2, "xlsx")
    assert res_ole2_xlsx == ArchivoInspeccionado(Veredicto.NO_SOPORTADO, motivo=MotivoDeEstado.ENCRYPTED_OR_LEGACY)

    # PDF con extensión docx
    res_pdf_docx = clasificar_por_firma(b"%PDF-1.4", "docx")
    assert res_pdf_docx == ArchivoInspeccionado(Veredicto.RECHAZADO, motivo=MotivoDeEstado.CONTENT_MISMATCH)


def test_macros_rechazadas():
    for ext in ("xlsm", "docm", "pptm"):
        res = clasificar_por_firma(b"PK\x03\x04", ext)
        assert res == ArchivoInspeccionado(Veredicto.RECHAZADO, motivo=MotivoDeEstado.MACRO_ENABLED)


def test_office_antiguo_no_soportado():
    for ext in ("doc", "xls"):
        res = clasificar_por_firma(_OLE2, ext)
        assert res == ArchivoInspeccionado(Veredicto.NO_SOPORTADO, motivo=MotivoDeEstado.LEGACY_FORMAT)


def test_formatos_no_soportados():
    for ext in ("zip", "rar", "dwg", ""):
        res = clasificar_por_firma(b"anything", ext)
        assert res == ArchivoInspeccionado(Veredicto.NO_SOPORTADO, motivo=MotivoDeEstado.FORMAT_NOT_SUPPORTED)
