"""Clasificación e inspección de firmas mágicas en archivos de anexos (plan 233, decisión 4)."""

from dataclasses import dataclass
from enum import StrEnum

from app.domain.entities.attachment_processing import MotivoDeEstado


class Veredicto(StrEnum):
    OK = "ok"
    NO_SOPORTADO = "unsupported"
    RECHAZADO = "rejected"


class FormatoLegible(StrEnum):
    PDF = "pdf"
    IMAGEN = "image"
    DOCX = "docx"
    XLSX = "xlsx"


@dataclass(frozen=True)
class ArchivoInspeccionado:
    veredicto: Veredicto
    formato: FormatoLegible | None = None
    mime: str | None = None
    motivo: MotivoDeEstado | None = None


LARGO_DE_CABECERA = 1024  # la especificación PDF admite basura antes de %PDF- en el primer KB
_PDF = b"%PDF-"
_ZIP = b"PK\x03\x04"
_OLE2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # .doc/.xls, y también un .docx/.xlsx cifrado
EXTENSIONES_CON_MACROS = frozenset(
    {"docm", "dotm", "xlsm", "xltm", "xlam", "pptm", "potm", "ppsm"}
)
EXTENSIONES_DE_OFFICE_ANTIGUO = frozenset({"doc", "xls"})
EXTENSIONES_DE_IMAGEN = frozenset({"png", "jpg", "jpeg", "webp"})


def _mime_de_imagen(c: bytes) -> str | None:
    if c.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if c.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(c) >= 12 and c[:4] == b"RIFF" and c[8:12] == b"WEBP":
        return "image/webp"
    return None


def _rechazo(m: MotivoDeEstado) -> ArchivoInspeccionado:
    return ArchivoInspeccionado(Veredicto.RECHAZADO, motivo=m)


def _no_soportado(m: MotivoDeEstado) -> ArchivoInspeccionado:
    return ArchivoInspeccionado(Veredicto.NO_SOPORTADO, motivo=m)


def clasificar_por_firma(cabecera: bytes, ext: str) -> ArchivoInspeccionado:
    """Qué es el archivo según sus primeros bytes, contra la extensión oficial del anexo.

    La extensión la fijó la decisión 2 (tiene que calzar con la de Mercado Público);
    acá se comprueba que el contenido no mienta. Un .pdf que es un ejecutable no se
    manda a ninguna parte.
    """
    ext = ext.lower().lstrip(".")
    if ext in EXTENSIONES_CON_MACROS:
        return _rechazo(MotivoDeEstado.MACRO_ENABLED)
    if ext in EXTENSIONES_DE_OFFICE_ANTIGUO:
        return _no_soportado(MotivoDeEstado.LEGACY_FORMAT)
    if ext == "pdf":
        if _PDF in cabecera[:LARGO_DE_CABECERA]:
            return ArchivoInspeccionado(
                Veredicto.OK, FormatoLegible.PDF, "application/pdf"
            )
        return _rechazo(MotivoDeEstado.CONTENT_MISMATCH)
    if ext in EXTENSIONES_DE_IMAGEN:
        mime = _mime_de_imagen(cabecera)
        return (
            ArchivoInspeccionado(Veredicto.OK, FormatoLegible.IMAGEN, mime)
            if mime
            else _rechazo(MotivoDeEstado.CONTENT_MISMATCH)
        )
    if ext in ("docx", "xlsx"):
        if cabecera.startswith(_ZIP):
            return ArchivoInspeccionado(Veredicto.OK, FormatoLegible(ext))
        if cabecera.startswith(_OLE2):
            return _no_soportado(MotivoDeEstado.ENCRYPTED_OR_LEGACY)
        return _rechazo(MotivoDeEstado.CONTENT_MISMATCH)
    return _no_soportado(MotivoDeEstado.FORMAT_NOT_SUPPORTED)
