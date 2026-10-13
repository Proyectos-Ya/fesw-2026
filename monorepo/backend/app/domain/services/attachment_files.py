"""Reglas puras de los archivos de anexos (plan 233, decisión 2).

Sin base de datos ni almacenamiento: claves de objeto, mes del cupo, validación
contra el nombre oficial y qué archivo ve cada empresa.
"""

import re
from collections.abc import Iterable
from datetime import date, datetime
from uuid import UUID

from app.domain.entities.attachment_file import AttachmentFile, AttachmentFileStatus
from app.domain.entities.tender_attachment import AttachmentStatus, OfficialAttachment
from app.domain.errors.attachment_errors import (
    AttachmentExtensionMismatch,
    AttachmentNameMismatch,
)
from app.domain.services.attachment_names import extension_de, normalizar_nombre_anexo
from app.shared.datetime_utils import chile_date

MAX_ATTACHMENT_SIZE_BYTES = 50 * 1024 * 1024

_TIPO_POR_DEFECTO = "application/octet-stream"
# type/subtype de RFC 6838. Viaja como cabecera, así que no puede traer espacios
# ni saltos de línea.
_MIME = re.compile(r"[a-z0-9][a-z0-9!#$&^_.+-]{0,126}/[a-z0-9][a-z0-9!#$&^_.+-]{0,126}")
# Los estados en los que el objeto ya está en el almacenamiento y verificado.
_CON_ARCHIVO = frozenset({AttachmentFileStatus.STORED, AttachmentFileStatus.UNSUPPORTED})


def clave_privada(workspace_id: UUID, sha256: str, ext: str) -> str:
    """Clave del objeto de una empresa: depende de la empresa y del contenido, no del anexo."""
    return f"private/{workspace_id}/{sha256}" + (f".{ext}" if ext else "")


def clave_compartida(tender_id: UUID, mp_document_id: int, sha256: str, ext: str) -> str:
    """Clave del objeto una vez promovido a compartido (decisión 6)."""
    return f"shared/{tender_id}/{mp_document_id}/{sha256}" + (f".{ext}" if ext else "")


def mes_de_cuota(instante_utc: datetime) -> date:
    """Primer día del mes de calendario **de Chile** al que cuenta una subida.

    Nunca `datetime.now().month`: Railway corre en UTC y una máquina local en
    Chile, y la subida de las 23:30 del último día del mes cambiaría de mes.
    """
    return chile_date(instante_utc).replace(day=1)


def tipo_de_contenido(mime: str) -> str:
    """El `Content-Type` que declaró el navegador, o uno neutro si no es de fiar."""
    limpio = mime.strip().lower()
    return limpio if _MIME.fullmatch(limpio) else _TIPO_POR_DEFECTO


def tiene_archivo(archivo: AttachmentFile) -> bool:
    return archivo.status in _CON_ARCHIVO


def validar_archivo_para_anexo(anexo: OfficialAttachment, nombre_archivo: str) -> None:
    """No valida nombres ni extensiones: los archivos descargados de Mercado Público
    tienen nombres y formatos arbitrarios que no coinciden con los títulos oficiales."""
    return


def _prioridad(archivo: AttachmentFile, workspace_id: UUID | None) -> int | None:
    """Menor es mejor; `None` = esta empresa no debe verlo."""
    if archivo.status == AttachmentFileStatus.PURGED or not archivo.visible_para(workspace_id):
        return None
    propio = workspace_id is not None and archivo.workspace_id == workspace_id
    if archivo.status in _CON_ARCHIVO:
        return 0 if propio else 1
    # Lo que otra empresa está subiendo, o le rechazaron, no es asunto de esta.
    if not propio:
        return None
    return 2 if archivo.status == AttachmentFileStatus.UPLOADING else 3


def elegir_archivo_visible(
    archivos: Iterable[AttachmentFile], workspace_id: UUID | None
) -> AttachmentFile | None:
    """El archivo que representa al anexo para esta empresa.

    Primero el propio guardado, luego el compartido guardado, luego la subida en
    curso y por último el rechazo propio; entre iguales, el más reciente. El
    archivo privado de otra empresa no se devuelve nunca, aunque venga en la lista.
    """
    candidatos = [
        (prioridad, archivo)
        for archivo in archivos
        if (prioridad := _prioridad(archivo, workspace_id)) is not None
    ]
    if not candidatos:
        return None
    # Se comparan datetimes, nunca `.timestamp()` sobre un naive.
    return max(candidatos, key=lambda par: (-par[0], par[1].created_at))[1]


def estado_del_anexo(archivo: AttachmentFile | None) -> AttachmentStatus:
    """Estado que ve la persona: `missing` si no hay archivo, o el del archivo elegido."""
    if archivo is None or archivo.status == AttachmentFileStatus.PURGED:
        return AttachmentStatus.MISSING
    return AttachmentStatus(archivo.status.value)
