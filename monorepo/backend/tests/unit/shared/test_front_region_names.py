"""Traducción de una región escrita por una fuente externa al nombre del wizard.

El borrador de perfil prellena el `ChipSelect` de regiones, que compara strings
exactos: "Metropolitana de Santiago" no marca el chip "Metropolitana".
"""

import pytest

from app.shared.regions import CHILE_REGIONS, FRONT_REGION_NAMES, to_front_region_name


def test_hay_un_nombre_del_wizard_por_cada_region():
    assert set(FRONT_REGION_NAMES) == set(CHILE_REGIONS)


@pytest.mark.parametrize("region_id,nombre", sorted(FRONT_REGION_NAMES.items()))
def test_el_nombre_del_wizard_se_reconoce_como_su_propia_region(region_id, nombre):
    assert to_front_region_name(nombre) == nombre


@pytest.mark.parametrize(
    "cruda,esperada",
    [
        ("XIII REGION METROPOLITANA", "Metropolitana"),
        ("V REGION VALPARAISO", "Valparaíso"),
        ("VALPARAÍSO", "Valparaíso"),
        ("Libertador General Bernardo O'Higgins", "O'Higgins"),
    ],
)
def test_traduce_como_escriben_las_fuentes(cruda, esperada):
    assert to_front_region_name(cruda) == esperada


def test_region_desconocida_devuelve_none():
    assert to_front_region_name("MARTE") is None
