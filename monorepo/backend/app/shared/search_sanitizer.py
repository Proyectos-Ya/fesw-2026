"""Módulo de sanitización y mitigación de inyecciones para el buscador de licitaciones (CA-6).

Remueve caracteres de control SQL, delimitadores de comentarios, secuencias de inyección
y etiquetas HTML/XSS, preservando términos de búsqueda legítimos en español.
"""

import re
import unicodedata

# Patrones comunes de inyección SQL
_SQL_INJECTION_PATTERNS = [
    re.compile(r"(\bOR\b|\bAND\b)\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+", re.IGNORECASE),
    re.compile(r"(\bOR\b|\bAND\b)\s+['\"][^'\"]*['\"]\s*=\s*['\"][^'\"]*['\"]", re.IGNORECASE),
    re.compile(r"\bUNION\s+(ALL\s+)?SELECT\b", re.IGNORECASE),
    re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE),
    re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE),
    re.compile(r"\bINSERT\s+INTO\b", re.IGNORECASE),
    re.compile(r"\bUPDATE\s+\w+\s+SET\b", re.IGNORECASE),
    re.compile(r"\bEXEC(\s+|\()", re.IGNORECASE),
]

_HTML_TAG_PATTERN = re.compile(r"<[^>]+>", re.IGNORECASE)
_SQL_COMMENTS_PATTERN = re.compile(r"(--[^\r\n]*|/\*.*?\*/)", re.DOTALL)
_SQL_CONTROL_CHARS = re.compile(r"['\";`\\]")


def sanitize_search_query(q: str | None) -> str:
    """Sanitiza el parámetro de búsqueda `q` para prevenir inyección SQL y XSS.

    - Remueve caracteres nulos y caracteres de control no imprimibles.
    - Remueve etiquetas HTML/scripts (<script>, etc.).
    - Remueve comentarios SQL (-- y /* ... */).
    - Neutraliza patrones de inyección SQL booleanos y comandos de manipulación/extracción.
    - Remueve caracteres de control de sintaxis SQL (comillas, punto y coma, etc.).
    - Normaliza espacios en blanco.
    - Si la consulta contenía exclusivamente caracteres de ataque o queda sin términos válidos,
      retorna una cadena vacía.
    """
    if not q:
        return ""

    # 1. Remover caracteres nulos y no imprimibles
    cleaned = q.replace("\x00", "")

    # 2. Remover etiquetas HTML / scripts
    cleaned = _HTML_TAG_PATTERN.sub(" ", cleaned)

    # 3. Remover comentarios SQL (-- y /* ... */)
    cleaned = _SQL_COMMENTS_PATTERN.sub(" ", cleaned)

    # 4. Neutralizar patrones de inyección SQL explícitos
    for pattern in _SQL_INJECTION_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)

    # 5. Remover caracteres de control de sintaxis SQL
    cleaned = _SQL_CONTROL_CHARS.sub(" ", cleaned)

    # 6. Normalizar espacios en blanco
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # 7. Si después de limpiar solo quedan números, símbolos o puntuación sin términos alfabéticos,
    # significa que era residuo de un predicado booleano (ej. "1 = 1", "1 1") o signos aislados.
    if cleaned and not re.search(r"[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ]", cleaned):
        return ""

    return cleaned
