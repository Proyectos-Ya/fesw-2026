"""Traducción de una región escrita por una fuente externa al nombre del wizard.

El borrador de perfil prellena el `ChipSelect` de regiones, que compara strings
exactos. El wizard usa los nombres canónicos, así que "Metropolitana" debe
llegar como "Metropolitana de Santiago" o el chip queda sin marcar.
"""

import pytest

from app.shared.regions import CHILE_REGIONS, to_front_region_name


@pytest.mark.parametrize("region_id,nombre", sorted(CHILE_REGIONS.items()))
def test_el_nombre_del_wizard_se_reconoce_como_su_propia_region(region_id, nombre):
    assert to_front_region_name(nombre) == nombre


@pytest.mark.parametrize(
    "cruda,esperada",
    [
        ("XIII REGION METROPOLITANA", "Metropolitana de Santiago"),
        ("V REGION VALPARAISO", "Valparaíso"),
        ("VALPARAÍSO", "Valparaíso"),
        ("O'Higgins", "Libertador General Bernardo O'Higgins"),
    ],
)
def test_traduce_como_escriben_las_fuentes(cruda, esperada):
    assert to_front_region_name(cruda) == esperada


def test_region_desconocida_devuelve_none():
    assert to_front_region_name("MARTE") is None
