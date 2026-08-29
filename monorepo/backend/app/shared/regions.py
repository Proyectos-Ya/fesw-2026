"""Fuente de verdad única de las regiones de Chile.

Las dos APIs de Mercado Público entregan la región de forma distinta:

* **Compra Ágil** manda el id numérico en `institucion.region` → `to_region_id`.
* **Licitaciones** manda el nombre en texto, con variantes de grafía, números
  romanos y abreviaturas → `normalize_region_name`.

Ambas puertas resuelven al mismo id administrativo (1 a 16), que es lo que
viaja al filtro: `buyer_institution.region_id` en SQL y el payload indexado
`region_id` en Qdrant. Vivir en un solo archivo evita el problema que ya
apareció una vez: dos numeraciones paralelas que no coincidían en ninguna
región, y licitaciones de la Metropolitana etiquetadas como "Los Ríos".
"""

import re
import unicodedata
from collections.abc import Sequence

# Numeración administrativa, verificada contra la API el 21 de agosto de 2026.
# `name` es el nombre canónico que se siembra en la tabla `region`; los alias
# solo se usan para reconocer texto de entrada, nunca para escribir.
CHILE_REGIONS: dict[int, str] = {
    1: "Tarapacá",
    2: "Antofagasta",
    3: "Atacama",
    4: "Coquimbo",
    5: "Valparaíso",
    6: "Libertador General Bernardo O'Higgins",
    7: "Maule",
    8: "Biobío",
    9: "La Araucanía",
    10: "Los Lagos",
    11: "Aysén del General Carlos Ibáñez del Campo",
    12: "Magallanes y de la Antártica Chilena",
    13: "Metropolitana de Santiago",
    14: "Los Ríos",
    15: "Arica y Parinacota",
    16: "Ñuble",
}

# Variantes con que la API de Licitaciones (y el frontend) nombran cada región:
# número romano, arábigo, capital regional y abreviaturas de uso corriente.
CHILE_REGION_ALIASES: dict[int, tuple[str, ...]] = {
    1: ("tarapaca", "i", "1", "iquique"),
    2: ("antofagasta", "ii", "2"),
    3: ("atacama", "iii", "3", "copiapo"),
    4: ("coquimbo", "iv", "4", "la serena"),
    5: ("valparaiso", "v", "5"),
    6: ("ohiggins", "o'higgins", "libertador", "rancagua", "vi", "6"),
    7: ("maule", "talca", "vii", "7"),
    8: ("biobio", "bio-bio", "concepcion", "viii", "8"),
    9: ("araucania", "la araucania", "temuco", "ix", "9"),
    10: ("los lagos", "puerto montt", "x", "10"),
    11: ("aysen", "coyhaique", "xi", "11"),
    12: ("magallanes", "punta arenas", "xii", "12"),
    13: ("metropolitana", "metropolitana de santiago", "santiago", "rm", "xiii", "13"),
    14: ("los rios", "valdivia", "la union", "xiv", "14"),
    15: ("arica y parinacota", "arica", "xv", "15"),
    16: ("nuble", "chillan", "xvi", "16"),
}

# Fila de respaldo para licitaciones cuya región no llega en la respuesta.
# `buyer_institution.region_id` es clave foránea, así que necesita apuntar a
# algo; un id propio deja el caso visible en vez de disfrazarlo de región real.
UNKNOWN_REGION_ID = 0
UNKNOWN_REGION_NAME = "Desconocida"


def _clean(text: str) -> str:
    """Baja a minúsculas, quita tildes y el prefijo "Región de/del"."""
    nfkd = unicodedata.normalize("NFKD", text)
    cleaned = "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()
    return re.sub(r"^region\s+(de\s+|del\s+)?", "", cleaned).strip()


# Índice inverso nombre canónico -> id, para el borde HTTP: el frontend filtra
# por nombre y el criterio de búsqueda usa ids.
_REGION_ID_BY_NORMALIZED_NAME = {
    name.strip().casefold(): region_id for region_id, name in CHILE_REGIONS.items()
}


def region_id_by_name(name: str) -> int | None:
    """Resuelve el id por el nombre canónico exacto. `None` si no existe.

    Comparación estricta: la usa el borde HTTP, donde un nombre que no calza
    debe ser un 400 y no una adivinanza.
    """
    return _REGION_ID_BY_NORMALIZED_NAME.get(name.strip().casefold())


def to_region_id(raw: object) -> int:
    """Puerta de entrada de **Compra Ágil**: `institucion.region` es un entero.

    Un valor ausente, no numérico o fuera del rango de las 16 regiones cae en
    `UNKNOWN_REGION_ID`: es preferible que el caso se vea a que la licitación
    quede archivada bajo una región real que no le corresponde.
    """
    try:
        region_id = int(raw)  # type: ignore[arg-type] 
    except (TypeError, ValueError):
        return UNKNOWN_REGION_ID
    return region_id if region_id in CHILE_REGIONS else UNKNOWN_REGION_ID


def normalize_region_name(raw_name: str | None) -> int | None:
    """Puerta de entrada de **Licitaciones**: la región llega como texto libre.

    Reconoce el nombre canónico, los alias, el número romano y el arábigo.
    Devuelve `None` si no reconoce nada, para que quien llame decida si eso es
    un descarte o un `UNKNOWN_REGION_ID`.
    """
    if not raw_name or not isinstance(raw_name, str):
        return None

    cleaned = _clean(raw_name)
    if not cleaned:
        return None

    for region_id, name in CHILE_REGIONS.items():
        if cleaned == _clean(name) or cleaned in CHILE_REGION_ALIASES[region_id]:
            return region_id

    # Coincidencia por subcadena como último recurso ("gobierno regional del
    # maule"). Se exige alias de más de 3 caracteres para no aceptar que "i" o
    # "x" dentro de cualquier palabra resuelvan a una región.
    for region_id, aliases in CHILE_REGION_ALIASES.items():
        if any(len(alias) > 3 and alias in cleaned for alias in aliases):
            return region_id

    return None


def canonical_region_name(region_id: int) -> str:
    """Nombre canónico de una región por su id."""
    return CHILE_REGIONS.get(region_id, UNKNOWN_REGION_NAME)


def are_regions_matching(
    target_region: str | None,
    allowed_regions: Sequence[str] | None,
) -> bool:
    """¿`target_region` cae dentro de `allowed_regions`?

    Compara ids, no strings: ambos lados pasan por `normalize_region_name`, así
    que "RM", "XIII" y "Región Metropolitana de Santiago" son la misma región.
    Sin `allowed_regions` no hay restricción y devuelve `True`.
    """
    if not allowed_regions:
        return True

    target_id = normalize_region_name(target_region)
    if target_id is None:
        return False

    return any(normalize_region_name(a) == target_id for a in allowed_regions)
