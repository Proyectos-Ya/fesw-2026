"""Nombre de archivo de un anexo, comparable entre Mercado Público y una subida.

Lo usa hoy la lista oficial (columna `name_normalized`) y lo usará la subida
manual (plan 233, decisión 2) para validar que el archivo es el anexo que dice ser.
Las dos puntas pasan por la misma función, así que basta con que sea determinista.
"""

import re
import unicodedata

# Sufijo que agrega el navegador al descargar dos veces el mismo archivo:
# "Bases (1).pdf" en Chrome y Edge, "Bases(1).pdf" en Firefox. Solo dígitos:
# "anexos (1,1-A, 2).docx" es un nombre oficial real y se conserva.
_SUFIJO_DESCARGA = re.compile(r"(?:\s*\(\d{1,3}\))+$")
_ESPACIOS = re.compile(r"\s+")
# Al menos una letra: "Versión 1.2" no tiene extensión "2".
_EXTENSION = re.compile(r"(?=[a-z0-9]*[a-z])[a-z0-9]{1,10}")


def _basico(nombre: str) -> str:
    """NFC, casefold, sin tildes y con los espacios colapsados."""
    texto = unicodedata.normalize("NFC", nombre).casefold()
    sin_marcas = "".join(
        c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c)
    )
    return _ESPACIOS.sub(" ", unicodedata.normalize("NFC", sin_marcas)).strip()


def _partir(base: str) -> tuple[str, str]:
    """Separa raíz y extensión; sin extensión reconocible devuelve (base, "")."""
    raiz, punto, ext = base.rpartition(".")
    ext = ext.strip()
    if not punto or not raiz.strip() or not _EXTENSION.fullmatch(ext):
        return base, ""
    return raiz.strip(), ext


def extension_de(nombre: str) -> str:
    """Extensión en minúsculas y sin punto; vacía si no hay una reconocible."""
    return _partir(_basico(nombre))[1]


def normalizar_nombre_anexo(nombre: str) -> str:
    """Forma canónica del nombre: sin mayúsculas, tildes ni sufijo de descarga repetida.

    Dos nombres **oficiales** distintos pueden normalizar igual (por ejemplo
    "Anexo.pdf" y "Anexo (2).pdf"). Por eso la validación de la subida
    (decisión 2) compara por `mp_document_id` + nombre normalizado, y no solo
    por nombre.
    """
    raiz, ext = _partir(_basico(nombre))
    raiz = _SUFIJO_DESCARGA.sub("", raiz).strip()
    return f"{raiz}.{ext}" if ext else raiz
