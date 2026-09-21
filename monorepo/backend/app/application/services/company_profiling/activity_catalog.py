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
from functools import lru_cache
from pathlib import Path

_CATALOG_PATH = Path(__file__).resolve().parent / "sii_activity_catalog.json"


@lru_cache(maxsize=1)
def _descriptions() -> dict[int, str]:
    rows = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    return {int(row["codigo"]): str(row["glosa"]) for row in rows}


def official_description(code: int) -> str:
    """Glosa oficial del código. Cadena vacía si no está en el catálogo."""
    return _descriptions().get(code, "")


def catalog_size() -> int:
    return len(_descriptions())
