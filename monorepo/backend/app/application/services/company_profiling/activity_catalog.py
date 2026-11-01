"""Catálogo oficial de actividades económicas del SII.

`sii_activity_catalog.json` es el xlsx del SII procesado en el spike 1
(`spikes/spike-1/poc/cargar_catalogo.py`) y verificado contra sii.cl: 674 códigos,
sin diferencias. Los códigos se guardan como enteros, así que un `011101` es
`11101` —igual que como lo entregan las fuentes.

Hace falta porque SRE entrega solo los códigos, sin glosa, y el clasificador de
rubro necesita texto. Se prefiere la glosa oficial también cuando la fuente sí trae
una: Web Empresario la entrega con la codificación rota en algunos campos.
"""

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

_CATALOG_PATH = Path(__file__).resolve().parent / "sii_activity_catalog.json"

_NOISE_PREFIXES = (
    r"^OTRAS ACTIVIDADES DE VENTA AL POR MENOR EN COMERCIOS NO ESPECIALIZADOS CON SURTIDO COMPUESTO PRINCIPALMENTE POR\s+",
    r"^VENTA AL POR MAYOR Y AL POR MENOR DE\s+",
    r"^VENTA AL POR MENOR DE\s+",
    r"^VENTA AL POR MAYOR DE\s+",
    r"^VENTA DE\s+",
    r"^COMERCIO AL POR MENOR DE\s+",
    r"^COMERCIO AL POR MAYOR DE\s+",
    r"^ACTIVIDADES DE SERVICIOS VINCULADAS AL\s+",
    r"^ACTIVIDADES DE SERVICIOS VINCULADAS A LA\s+",
    r"^ACTIVIDADES DE APOYO A LA\s+",
    r"^ACTIVIDADES DE APOYO AL\s+",
    r"^OTRAS ACTIVIDADES DE\s+",
    r"^ACTIVIDADES DE\s+",
    r"^SERVICIOS DE\s+",
    r"^ELABORACI[OÓ]N DE\s+",
    r"^FABRICACI[OÓ]N DE\s+",
)

_NOISE_SUFFIXES = (
    r"\s+EN COMERCIOS ESPECIALIZADOS.*$",
    r"\s+EN COMERCIOS NO ESPECIALIZADOS.*$",
    r"\s+EN PUESTOS DE VENTA Y MERCADOS.*$",
    r"\s+A CAMBIO DE UNA RETRIBUCI[OÓ]N O POR CONTRATA.*$",
    r"\s+N\.C\.P\.?$",
    r"\s+EXCEPTO.*$",
)


def _normalize_lookup_key(text: str) -> str:
    stripped = unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("ascii")
    return " ".join(stripped.upper().split())


@lru_cache(maxsize=1)
def _rows() -> list[dict[str, Any]]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _descriptions() -> dict[int, str]:
    return {int(row["codigo"]): str(row["glosa"]) for row in _rows()}


@lru_cache(maxsize=1)
def _groups() -> dict[int, str]:
    return {int(row["codigo"]): str(row.get("grupo_titulo", "")) for row in _rows()}


@lru_cache(maxsize=1)
def _codes_by_glosa() -> dict[str, int]:
    return {_normalize_lookup_key(str(row["glosa"])): int(row["codigo"]) for row in _rows()}


def official_description(code: int) -> str:
    """Glosa oficial del código. Cadena vacía si no está en el catálogo."""
    return _descriptions().get(code, "")


def group_title(code: int) -> str:
    """Subrubro (`grupo_titulo`) oficial del código en el clasificador del SII."""
    return _groups().get(code, "")


def code_for_description(description: str) -> int | None:
    """Busca el código SII cuya glosa oficial coincide (sin tildes ni mayúsculas)."""
    if not description or not description.strip():
        return None
    return _codes_by_glosa().get(_normalize_lookup_key(description))


def clean_sii_keywords(text: str) -> list[str]:
    """Limpia prefijos y sufijos tributarios de una glosa o subrubro del SII."""
    cleaned = re.sub(r"\s*\([^)]*\)", "", text.strip())
    for pattern in _NOISE_SUFFIXES:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    for pattern in _NOISE_PREFIXES:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    parts = re.split(r"\s*(?:;|,|\bY DE\b|\bO DE\b|\bE\b)\s*", cleaned, flags=re.IGNORECASE)
    result: list[str] = []
    for part in parts:
        phrase = part.strip().lower()
        if len(phrase) >= 4 and phrase not in result:
            result.append(phrase)
    return result


def fallback_keywords_for_code(code: int, fallback_description: str = "") -> list[str]:
    """Extrae palabras clave desde la glosa y el subrubro (`grupo_titulo`) del código."""
    glosa = official_description(code) or fallback_description
    subrubro = group_title(code)
    keywords: list[str] = []
    for source_text in (glosa, subrubro):
        if not source_text:
            continue
        for kw in clean_sii_keywords(source_text):
            if kw not in keywords:
                keywords.append(kw)
    return keywords


def catalog_size() -> int:
    return len(_descriptions())
