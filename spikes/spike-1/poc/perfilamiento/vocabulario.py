"""Vocabularios cerrados del producto: los rubros y las regiones del front.

Por qué se leen del front y no se copian acá
--------------------------------------------
`Supplier.sectors` es `list[str]` sin restricción, y `profileSchema.ts` solo
exige "al menos un rubro". O sea: **nada en el sistema impide escribir un sector
que no existe**. Si el borrador automático inventa "Construcción" cuando la lista
dice "Obras de Construcción e Infraestructura", el perfil se guarda igual, el
usuario ve su rubro sin marcar en el wizard y nadie recibe un error.

Por eso el diccionario del spike no puede tener su propia lista de rubros: tiene
que apuntar a la del front. Se lee del archivo original en vez de copiarlo, así
que si alguien agrega un rubro allá, las pruebas de acá lo ven.

Los archivos son TypeScript, no JSON, así que se extraen con una expresión
regular. Es frágil ante un cambio de formato — y está bien: preferimos que falle
ruidosamente a que siga con una lista desactualizada.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from puente_backend import RAIZ_BACKEND

# El front es hermano del backend dentro de `monorepo/`.
_DATOS_FRONT = (
    (RAIZ_BACKEND.parent / "frontend" / "src" / "features" / "company-profile" / "data")
    if RAIZ_BACKEND
    else None
)

_LITERAL = re.compile(r'"([^"]+)"')


def _leer_lista(archivo: str, constante: str) -> tuple[str, ...]:
    if _DATOS_FRONT is None:
        raise FileNotFoundError("no se encontró la raíz del repositorio")

    ruta = _DATOS_FRONT / archivo
    contenido = ruta.read_text(encoding="utf-8")
    # Se busca desde el `= [` y no desde el nombre de la constante: la anotación
    # de tipo `readonly string[]` trae un `]` que corta el bloque antes de
    # empezar.
    bloque = re.search(
        rf"{constante}\s*:[^=]*=\s*\[(.*?)\]", contenido, re.DOTALL
    )
    if bloque is None:
        raise ValueError(f"{ruta} ya no declara {constante} como arreglo literal")
    valores = tuple(_LITERAL.findall(bloque.group(1)))
    if not valores:
        raise ValueError(f"{ruta}: no se pudo extraer ningún valor de {constante}")
    return valores


@lru_cache(maxsize=1)
def sectores() -> tuple[str, ...]:
    """Los rubros que el usuario puede elegir en el wizard."""
    return _leer_lista("sectors.ts", "SECTORS")


@lru_cache(maxsize=1)
def regiones() -> tuple[str, ...]:
    """Las regiones tal como las escribe el front."""
    return _leer_lista("regions.ts", "REGIONS")


def es_sector_valido(nombre: str) -> bool:
    return nombre in sectores()


def a_region_del_front(nombre_backend: str) -> str | None:
    """Traduce el nombre canónico del backend al que usa el front.

    Los dos vocabularios no coinciden: el backend dice
    "Metropolitana de Santiago" y "Libertador General Bernardo O'Higgins", el
    front dice "Metropolitana" y "O'Higgins". Ninguno está mal — son para cosas
    distintas—, pero un borrador que prellena el wizard tiene que hablar el del
    front, o la región llega y no queda marcada.

    Se traduce pasando ambos lados por `normalize_region_name`, que es el
    normalizador que ya existe en el backend, en vez de escribir una tabla de
    equivalencias que habría que mantener sincronizada.
    """
    from app.shared.regions import normalize_region_name

    objetivo = normalize_region_name(nombre_backend)
    if objetivo is None:
        return None
    for nombre_front in regiones():
        if normalize_region_name(nombre_front) == objetivo:
            return nombre_front
    return None
