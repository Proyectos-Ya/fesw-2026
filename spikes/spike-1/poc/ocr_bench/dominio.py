"""Puente hacia el dominio del backend, para no reimplementar lo que ya existe.

`is_valid_rut` ya está en `app/domain/entities/supplier.py` con el dígito
verificador módulo 11. Copiarlo acá sería crear una segunda versión que puede
divergir justo en el detalle que importa (el caso K), y el spike estaría midiendo
su propia copia en vez del validador real.

La ubicación de la raíz del backend la resuelve `puente_backend`, que es común a
todo el PoC.
"""

from __future__ import annotations

from puente_backend import RAIZ_BACKEND, asegurar_path

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
