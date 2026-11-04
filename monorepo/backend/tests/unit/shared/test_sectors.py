"""Términos significativos de un rubro para el peso de rubro (plan 311, CA 1).

Los nombres del catálogo ONU repiten palabras como "Servicios", "Equipos" o
"Artículos", que aparecen en casi toda licitación. Si cuentan, casi todas las
empresas suman el peso de rubro contra casi todas las licitaciones.
"""

import pytest

from app.shared.sectors import PRODUCT_SECTORS, significant_terms


def test_quita_las_palabras_genericas():
    assert significant_terms("Servicios de limpieza industrial") == ["limpieza"]


def test_quita_puntuacion_y_tildes():
    assert significant_terms(
        "Tecnologías de la información, telecomunicaciones y radiodifusión"
    ) == ["tecnologias", "informacion", "telecomunicaciones", "radiodifusion"]


def test_no_repite_terminos():
    assert significant_terms("Equipos y suministros de limpieza, limpieza") == [
        "limpieza"
    ]


@pytest.mark.parametrize("sector", PRODUCT_SECTORS)
def test_todo_rubro_conserva_al_menos_un_termino(sector):
    """Si alguno queda vacío, se ajusta la lista de genéricas, no este test."""
    assert significant_terms(sector)
