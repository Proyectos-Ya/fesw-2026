"""Puente hacia el dominio del backend, para no reimplementar lo que ya existe.

`is_valid_rut` ya está en `app/domain/entities/supplier.py` con el dígito
verificador módulo 11. Copiarlo acá sería crear una segunda versión que puede
divergir justo en el detalle que importa (el caso K), y el spike estaría midiendo
su propia copia en vez del validador real.

La ubicación de la raíz del backend la resuelve `puente_backend`, que es común a
todo el PoC y vive en `poc/` (un nivel arriba de `ocr/`, donde está este
archivo). Se busca hacia arriba en vez de asumir que quien importe este módulo
ya dejó `poc/` en el `sys.path` — ese supuesto se rompió una vez, cuando
`ocr_bench/` se movió de `poc/` a `poc/ocr/ocr_bench/` y las importaciones
directas de este módulo (sin pasar por `benchmark.py`/`degradar.py`) dejaron de
encontrar `puente_backend`. Buscar el archivo en vez de contar niveles hace que
este módulo funcione igual sin importar desde dónde se lo importe.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _agregar_poc_al_path() -> None:
    for candidato in Path(__file__).resolve().parents:
        if (candidato / "puente_backend.py").is_file():
            ruta = str(candidato)
            if ruta not in sys.path:
                sys.path.insert(0, ruta)
            return


_agregar_poc_al_path()

from puente_backend import RAIZ_BACKEND, asegurar_path  # noqa: E402

try:
    asegurar_path()
    from app.domain.entities.supplier import is_valid_rut

    RUT_DISPONIBLE = True
    MOTIVO_RUT = ""
except ImportError as exc:  # pragma: no cover - depende del entorno
    RUT_DISPONIBLE = False
    MOTIVO_RUT = (
        f"no se pudo importar is_valid_rut (raíz detectada: {RAIZ_BACKEND}): "
        f"{exc}. Instalar pydantic en el entorno del PoC (está en requirements.txt)."
    )

    def is_valid_rut(rut: str) -> bool:  # type: ignore[misc]
        raise RuntimeError(MOTIVO_RUT)


__all__ = ["is_valid_rut", "RUT_DISPONIBLE", "MOTIVO_RUT", "RAIZ_BACKEND"]
