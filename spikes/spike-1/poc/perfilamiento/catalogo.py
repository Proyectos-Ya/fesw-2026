"""Datos oficiales por código, leídos del catálogo del SII ya procesado.

Es la fuente de verdad para cualquier código de actividad: glosa y sección,
**tal como aparecen en el xlsx real** (`cargar_catalogo.py` los extrajo ahí,
sin inventar ni calcular nada). Reemplaza el cálculo de sección por rangos de
división que tenía `ciiu.py`: ese cálculo existía porque este catálogo todavía
no se había procesado cuando se escribió el diccionario por primera vez, y ya
demostró que puede tener errores propios (la división 04 del cobre, un caso
chileno fuera del estándar CIIU internacional, que no se detectó hasta
comparar contra este mismo archivo). Consultar la sección real es más simple y
no puede tener ese tipo de error: es una lectura, no una cuenta.

Dos usos concretos:

1. **SRE no entrega glosa**, solo el código pelado (`"actecos": ["433000"]`).
   Sin esto no hay texto para generar `keywords` ni para detectar una glosa
   genérica.
2. **El diccionario genera sectores y palabras clave para cualquier código del
   catálogo**, no solo para los que se curaron a mano — ver `diccionario.py`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_RUTA_CATALOGO = Path(__file__).resolve().parent / "catalogo_sii.json"


@dataclass(frozen=True)
class FilaCatalogo:
    """Una fila del catálogo real del SII, sin transformar."""

    codigo: int
    glosa: str
    seccion_titulo: str
    grupo_titulo: str


@lru_cache(maxsize=1)
def _indice() -> dict[int, FilaCatalogo]:
    if not _RUTA_CATALOGO.exists():
        return {}
    filas = json.loads(_RUTA_CATALOGO.read_text(encoding="utf-8"))
    return {
        int(fila["codigo"]): FilaCatalogo(
            codigo=int(fila["codigo"]),
            glosa=str(fila["glosa"]),
            seccion_titulo=str(fila["seccion_titulo"]),
            grupo_titulo=str(fila["grupo_titulo"]),
        )
        for fila in filas
    }


def fila(codigo: int) -> FilaCatalogo | None:
    """La fila completa del catálogo para ese código. `None` si no existe."""
    return _indice().get(codigo)


def glosa_oficial(codigo: int) -> str:
    """Glosa del catálogo del SII para ese código. Cadena vacía si no está."""
    registro = fila(codigo)
    return registro.glosa if registro else ""


def seccion_titulo(codigo: int) -> str:
    """Título de sección **real**, tal como aparece en el xlsx del SII.

    No es una letra calculada: es texto leído directamente de la fuente
    (`"AGRICULTURA, GANADERÍA, SILVICULTURA Y PESCA"`, etc.), así que no puede
    tener el tipo de error que sí tuvo el cálculo por rangos de división.
    Cadena vacía si el código no está en el catálogo.
    """
    registro = fila(codigo)
    return registro.seccion_titulo if registro else ""
