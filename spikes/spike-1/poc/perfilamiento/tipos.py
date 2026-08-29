"""El tipo `Actividad` y utilidades de texto sobre la glosa del SII.

Este archivo se llamó `ciiu.py`. Se renombró porque, desde que se eliminó el
cálculo de sección (ver más abajo), el nombre ya no describe lo que hay acá —
la historia de por qué existió ese cálculo sigue siendo útil, pero un lector
nuevo no debería tener que adivinarla a partir del nombre del import.

Historia de este archivo
-------------------------
Originalmente calculaba la sección CIIU de un código con una tabla de rangos
de división que escribí de memoria (estándar CIIU Rev.4) — código → división →
letra de sección → nombre de rubro. Funcionaba, pero era una capa de cálculo
propia que podía tener errores: los tuvo (la división 04 del cobre, una
extensión chilena fuera del estándar internacional, no se detectó hasta
comparar contra el catálogo real).

**Ese cálculo se eliminó.** El catálogo real del SII, ya procesado en
`catalogo_sii.json`, trae la sección de cada código como texto — leerla es una
búsqueda en un diccionario, no una cuenta, y no puede tener ese tipo de error.
Ver `catalogo.seccion_titulo`.

Y para determinar el **rubro del producto** (no la sección CIIU), agrupar por
sección resultó demasiado grueso: una sola sección de "comercio" mete 105
códigos reales sin relación entre sí en el mismo rubro. Ver
`clasificador_rubro.py`, que mira la glosa de cada actividad puntual en vez de
su sección.

Lo que queda acá es lo que sigue siendo necesario sin depender de ninguna de
esas dos cosas: el tipo `Actividad` que viaja por todo el pipeline, y las dos
utilidades de texto sobre la glosa (detectar si es genérica, normalizarla a una
frase legible).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Marcas de glosa administrativa: categorías residuales del catálogo, que
# existen para que toda actividad tenga dónde caer y no para describir a qué se
# dedica una empresa. "n.c.p." es "no clasificado previamente".
#
# No se descartan en silencio: `Actividad.es_generica` las marca y quien llame
# decide. Un proveedor cuyas actividades son TODAS genéricas es un hallazgo —
# significa que para esa empresa la fuente no aporta nada al matching— y eso hay
# que poder verlo, no perderlo.
_MARCAS_GENERICAS = (
    "n.c.p",
    "ncp",
    "no clasificad",
    "no especificad",
    "no especializad",
    "otras actividades",
    "otros tipos",
    "otras industrias",
    "otro tipo",
)


def _sin_tildes(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def es_glosa_generica(glosa: str) -> bool:
    """¿Es una categoría residual del catálogo, sin contenido descriptivo?"""
    plano = _sin_tildes(glosa).lower()
    return any(marca in plano for marca in _MARCAS_GENERICAS)


@dataclass(frozen=True)
class Actividad:
    """Una actividad económica ya interpretada."""

    codigo: int
    glosa: str
    afecta_iva: bool = False
    desde: str = ""

    @property
    def es_generica(self) -> bool:
        return es_glosa_generica(self.glosa)


def normalizar_glosa(glosa: str) -> str:
    """Deja la glosa legible: de MAYÚSCULAS a una frase normal.

    La API la entrega íntegramente en mayúsculas y sin tildes
    (`"TERMINACION Y ACABADO DE EDIFICIOS"`). Va a terminar en `keywords`, así
    que conviene que se parezca a como está escrito el resto del perfil.

    No se le devuelven las tildes: hacerlo requeriría un diccionario y el riesgo
    de equivocarse es peor que el de dejarlo sin acentuar.
    """
    limpia = re.sub(r"\s+", " ", glosa).strip()
    if not limpia:
        return ""
    return limpia[0].upper() + limpia[1:].lower()
