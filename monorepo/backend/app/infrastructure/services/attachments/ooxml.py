"""Inspección de archivos OOXML (docx, xlsx) y extracción de texto de docx (plan 233, decisión 4)."""

import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from io import BytesIO

from app.domain.entities.attachment_processing import MotivoDeEstado
from app.domain.services.attachment_file_signatures import FormatoLegible

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_PARTE_PRINCIPAL = {
    FormatoLegible.DOCX: "word/document.xml",
    FormatoLegible.XLSX: "xl/workbook.xml",
}


@dataclass(frozen=True)
class LimitesZip:
    """Defensa contra zip bombs. El `zipfile` de CPython corta lo descomprimido en el tamaño
    declarado (DEFLATE), así que sumar los tamaños declarados acota la memoria. BZIP2 y LZMA
    descomprimen sin tope por bloque: se rechazan (Office no los usa)."""

    max_entradas: int = 2_000
    max_total_bytes: int = 200 * 1024 * 1024
    max_entrada_bytes: int = 100 * 1024 * 1024
    max_razon: int = 200  # descomprimido / comprimido
    razon_desde_bytes: int = 1024 * 1024  # la razón solo se mira en entradas de 1 MiB o más
    max_xml_bytes: int = 50 * 1024 * 1024  # lo que se carga entero en ElementTree


class ArchivoDemasiadoGrande(ValueError):
    pass


def leer_acotado(zf: zipfile.ZipFile, nombre: str, limite: int) -> bytes:
    with zf.open(nombre) as parte:
        datos = parte.read(limite + 1)
    if len(datos) > limite:
        raise ArchivoDemasiadoGrande(nombre)
    return datos


def inspeccionar_ooxml(
    datos: bytes,
    formato: FormatoLegible,
    limites: LimitesZip = LimitesZip(),
) -> MotivoDeEstado | None:
    """`None` si se puede leer; si no, el motivo para rechazarlo."""
    try:
        zf = zipfile.ZipFile(BytesIO(datos))
    except (zipfile.BadZipFile, ValueError):
        return MotivoDeEstado.CONTENT_MISMATCH
    with zf:
        entradas = zf.infolist()
        if len(entradas) > limites.max_entradas:
            return MotivoDeEstado.ARCHIVE_TOO_LARGE
        total = 0
        for e in entradas:
            if (
                e.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                or e.flag_bits & 0x1
            ):
                return MotivoDeEstado.CONTENT_MISMATCH
            if e.file_size > limites.max_entrada_bytes:
                return MotivoDeEstado.ARCHIVE_TOO_LARGE
            if (
                e.file_size >= limites.razon_desde_bytes
                and e.file_size > limites.max_razon * max(e.compress_size, 1)
            ):
                return MotivoDeEstado.ARCHIVE_TOO_LARGE
            total += e.file_size
            if total > limites.max_total_bytes:
                return MotivoDeEstado.ARCHIVE_TOO_LARGE
            if e.filename.lower().endswith("vbaproject.bin"):
                return MotivoDeEstado.MACRO_ENABLED
        nombres = {e.filename for e in entradas}
        parte_princ = _PARTE_PRINCIPAL.get(formato)
        if "[Content_Types].xml" not in nombres or parte_princ not in nombres:
            return MotivoDeEstado.CONTENT_MISMATCH
        try:
            tipos = leer_acotado(zf, "[Content_Types].xml", 1024 * 1024)
            if b"macroenabled" in tipos.lower():
                return MotivoDeEstado.MACRO_ENABLED
            if formato is FormatoLegible.DOCX:
                xml = leer_acotado(zf, "word/document.xml", limites.max_xml_bytes)
                # OOXML nunca trae DOCTYPE: si aparece, es un intento de entidades (billion laughs).
                if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
                    return MotivoDeEstado.CONTENT_MISMATCH
        except (ArchivoDemasiadoGrande, zipfile.BadZipFile, KeyError):
            return MotivoDeEstado.ARCHIVE_TOO_LARGE
    return None


def _texto_parrafo(p: ET.Element) -> str:
    partes: list[str] = []
    for el in p.iter():
        if el.tag == _W + "t" and el.text:
            partes.append(el.text)
        elif el.tag == _W + "tab":
            partes.append("\t")
        elif el.tag in (_W + "br", _W + "cr"):
            partes.append("\n")
    return "".join(partes).strip()  # w:delText no se lee


def _bloques(contenedor: ET.Element) -> Iterator[str]:
    for hijo in contenedor:
        if hijo.tag == _W + "p":
            if texto := _texto_parrafo(hijo):
                yield texto
        elif hijo.tag == _W + "tbl":
            for fila in hijo.findall(_W + "tr"):  # solo hijas directas
                celdas = [
                    " ".join(_bloques(celda))
                    for celda in fila.findall(_W + "tc")
                ]
                if any(celdas):
                    yield " | ".join(celdas)
        elif hijo.tag == _W + "sdt":
            if (contenido := hijo.find(_W + "sdtContent")) is not None:
                yield from _bloques(contenido)


def docx_a_texto(datos: bytes, limites: LimitesZip = LimitesZip()) -> str:
    """Texto del cuerpo de un .docx en orden de lectura. Supone que `inspeccionar_ooxml` ya lo aceptó."""
    with zipfile.ZipFile(BytesIO(datos)) as zf:
        xml = leer_acotado(zf, "word/document.xml", limites.max_xml_bytes)
    cuerpo = ET.fromstring(xml).find(_W + "body")
    return "" if cuerpo is None else "\n".join(_bloques(cuerpo))
