import re
import unicodedata
from typing import Any, Optional, Sequence

CHILEAN_REGIONS: dict[int, dict[str, Any]] = {
    1: {"name": "Región de Tarapacá", "aliases": ["tarapaca", "i", "1"]},
    2: {"name": "Región de Antofagasta", "aliases": ["antofagasta", "ii", "2"]},
    3: {"name": "Región de Atacama", "aliases": ["atacama", "iii", "3"]},
    4: {"name": "Región de Coquimbo", "aliases": ["coquimbo", "iv", "4"]},
    5: {"name": "Región de Valparaíso", "aliases": ["valparaiso", "v", "5"]},
    6: {"name": "Región del Libertador General Bernardo O'Higgins", "aliases": ["ohiggins", "o'higgins", "libertador", "rancagua", "vi", "6"]},
    7: {"name": "Región del Maule", "aliases": ["maule", "talca", "vii", "7"]},
    8: {"name": "Región del Biobío", "aliases": ["biobio", "bio-bio", "concepcion", "viii", "8"]},
    9: {"name": "Región de La Araucanía", "aliases": ["araucania", "la araucania", "temuco", "ix", "9"]},
    10: {"name": "Región de Los Lagos", "aliases": ["los lagos", "puerto montt", "x", "10"]},
    11: {"name": "Región de Aysén del General Carlos Ibáñez del Campo", "aliases": ["aysen", "coyhaique", "xi", "11"]},
    12: {"name": "Región de Magallanes y de la Antártica Chilena", "aliases": ["magallanes", "punta arenas", "xii", "12"]},
    13: {"name": "Región Metropolitana de Santiago", "aliases": ["metropolitana", "metropolitana de santiago", "santiago", "rm", "xiii", "13"]},
    14: {"name": "Región de Los Ríos", "aliases": ["los rios", "valdivia", "la union", "xiv", "14"]},
    15: {"name": "Región de Arica y Parinacota", "aliases": ["arica y parinacota", "arica", "xv", "15"]},
    16: {"name": "Región de Ñuble", "aliases": ["nuble", "chillan", "xvi", "16"]},
}


def _clean_text(text: str) -> str:
    """Normaliza un texto eliminando tildes, signos y prefijos comunes."""
    if not text:
        return ""
    # Remover tildes
    nfkd = unicodedata.normalize("NFKD", text)
    cleaned = "".join([c for c in nfkd if not unicodedata.combining(c)]).lower().strip()
    # Remover prefijos de región
    cleaned = re.sub(r"^(region\s+de\s+|region\s+del\s+|region\s+)", "", cleaned).strip()
    return cleaned


def normalize_region_name(raw_name: Optional[str]) -> Optional[int]:
    """
    Convierte cualquier nombre, alias o número de región en Chile a su ID oficial (1 al 16).
    Retorna None si no se reconoce.
    """
    if not raw_name or not isinstance(raw_name, str):
        return None

    cleaned = _clean_text(raw_name)
    if not cleaned:
        return None

    # Búsqueda exacta en alias y nombres
    for reg_id, data in CHILEAN_REGIONS.items():
        canonical_clean = _clean_text(data["name"])
        if cleaned == canonical_clean or cleaned in data["aliases"]:
            return reg_id

    # Búsqueda por subcadena relevante
    for reg_id, data in CHILEAN_REGIONS.items():
        for alias in data["aliases"]:
            if len(alias) > 3 and alias in cleaned:
                return reg_id

    return None


def get_canonical_region_name(region_id: int) -> str:
    """Retorna el nombre canónico de la región dado su ID."""
    if region_id in CHILEAN_REGIONS:
        return CHILEAN_REGIONS[region_id]["name"]
    return "Región Desconocida"


def are_regions_matching(
    target_region: Optional[str],
    allowed_regions: Optional[Sequence[str]],
) -> bool:
    """
    Determina si `target_region` coincide con alguna de las `allowed_regions`.
    Si `allowed_regions` está vacío o es None, se considera que no hay restricción (True).
    """
    if not allowed_regions:
        return True

    target_id = normalize_region_name(target_region)
    if target_id is None:
        return False

    for allowed in allowed_regions:
        allowed_id = normalize_region_name(allowed)
        if allowed_id is not None and target_id == allowed_id:
            return True

    return False
