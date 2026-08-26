"""Puente hacia el paquete `app` del backend, para no reimplementar lo que existe.

El PoC vive fuera de `monorepo/backend/`, así que hay que agregar esa raíz al
`sys.path` antes de importar cualquier cosa del dominio. La flecha va en un solo
sentido: nada de producción importa este directorio.

La raíz se **busca hacia arriba** en vez de contarse en saltos de directorio. El
spike es material descartable y ya cambió de lugar dos veces
(`monorepo/backend/docs/spike-1/` -> `project-data/spike-1/` -> `spikes/spike-1/`);
contar saltos se rompe en silencio con cada movimiento, y un PoC que mide con su
propia copia de las reglas del dominio no mide el producto.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Marca que identifica la raíz del repositorio sin ambigüedad: la carpeta que
# contiene el paquete `app` con el dominio.
_MARCA = Path("monorepo") / "backend" / "app" / "domain"


def _buscar_raiz_backend() -> Path | None:
    for candidato in Path(__file__).resolve().parents:
        if (candidato / _MARCA).is_dir():
            return candidato / "monorepo" / "backend"
    return None


RAIZ_BACKEND = _buscar_raiz_backend()


def asegurar_path() -> None:
    """Deja el backend importable. Lanza `ImportError` si no se encontró."""
    if RAIZ_BACKEND is None:
        raise ImportError(
            "no se encontró la raíz del backend subiendo desde "
            f"{Path(__file__).resolve()}. ¿Se movió el PoC fuera del repositorio?"
        )
    ruta = str(RAIZ_BACKEND)
    if ruta not in sys.path:
        sys.path.insert(0, ruta)
