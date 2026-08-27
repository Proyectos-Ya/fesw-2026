"""Rellena las variables obligatorias que falten, para que pytest pueda arrancar.

El problema que resuelve: `tests/conftest.py` hace `from app.main import app`, y
eso ejecuta `Settings()` a nivel de módulo. Sin un `.env` completo, pytest falla
**en la recolección** —no en un test— con un error que parece un defecto del
código y no lo es. Mientras eso siguiera así no se podía montar CI, donde no hay
`.env` en absoluto.

Este archivo vive en la raíz del backend a propósito: pytest carga los
`conftest.py` de los directorios padre antes que los de `tests/`, así que las
variables quedan puestas antes de que nadie importe `app`.

**Solo rellena huecos.** Si el valor ya viene del entorno o del `.env` del
desarrollador, no se toca. Esto importa: los tests de integración necesitan las
credenciales reales de Postgres, y pisarlas con un valor de mentira los rompería
en vez de arreglarlos.
"""

import os
from pathlib import Path

from dotenv import dotenv_values

from pytest_env_defaults import RELLENO_ENV

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def _completar_variables_faltantes() -> None:
    del_archivo = dotenv_values(_ENV_FILE) if _ENV_FILE.exists() else {}
    for clave, valor in RELLENO_ENV.items():
        if not (os.environ.get(clave) or del_archivo.get(clave)):
            os.environ[clave] = valor


_completar_variables_faltantes()
