"""Los rubros del wizard son los mismos que guarda el backend (plan 311, CA 1).

`frontend/src/features/company-profile/data/sectors.ts` es una copia de
`SECTOR_GROUPS`. Un rubro que exista en una y no en la otra se guarda igual, pero en
el wizard aparece sin marcar o en otro grupo, y nada más falla.

El test lee el `.ts` con expresiones regulares sobre el formato fijo que documenta
su cabecera: cada grupo abre con `title: "..."` y cada rubro va solo en su línea,
entre comillas dobles. Necesita el repositorio completo; corre en el job
`test-unit-backend` del CI, no en la imagen Docker del backend.
"""

import re
from pathlib import Path

from app.shared.sectors import SECTOR_GROUPS

SECTORS_TS = (
    Path(__file__).resolve().parents[3]
    / "frontend/src/features/company-profile/data/sectors.ts"
)

_TITLE = re.compile(r'^\s*title:\s*"([^"]+)",?\s*$')
_SECTOR = re.compile(r'^\s*"([^"]+)",\s*$')


def _frontend_groups() -> list[tuple[str, list[str]]]:
    groups: list[tuple[str, list[str]]] = []
    for line in SECTORS_TS.read_text(encoding="utf-8").splitlines():
        if title := _TITLE.match(line):
            groups.append((title.group(1), []))
        elif (sector := _SECTOR.match(line)) and groups:
            groups[-1][1].append(sector.group(1))
    return groups


def test_el_frontend_tiene_los_mismos_grupos_y_rubros_en_el_mismo_orden():
    backend = [(group.title, list(group.sectors)) for group in SECTOR_GROUPS]
    assert _frontend_groups() == backend


def test_el_lector_encuentra_todos_los_rubros():
    """Si el formato del `.ts` cambia, el test de arriba no debe pasar por vacío."""
    assert sum(len(sectors) for _, sectors in _frontend_groups()) == 58
