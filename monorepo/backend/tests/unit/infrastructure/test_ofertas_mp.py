"""El total de ofertas recibidas se lee igual en el listado y en el detalle."""

import json
from pathlib import Path
from typing import Any

import pytest

from app.infrastructure.services.tenders.ofertas import leer_total_ofertas

FIXTURE = Path(__file__).parents[2] / "fixtures" / "mp_listado_cambios.json"


def _con_total(valor: object) -> dict[str, Any]:
    return {"resumen": {"total_ofertas_recibidas": valor}}


class TestItemsReales:
    def test_el_fixture_trae_cero_diecisiete_uno_y_cero(self):
        datos = json.loads(FIXTURE.read_text(encoding="utf-8"))
        totales = [leer_total_ofertas(i) for i in datos["payload"]["items"]]
        assert totales == [0, 17, 1, 0]


class TestValores:
    @pytest.mark.parametrize("valor, esperado", [(0, 0), (17, 17)])
    def test_un_entero_no_negativo_se_lee_tal_cual(self, valor, esperado):
        assert leer_total_ofertas(_con_total(valor)) == esperado

    @pytest.mark.parametrize("valor", [None, True, False, -1, "17", 17.0])
    def test_un_total_raro_no_se_inventa(self, valor):
        assert leer_total_ofertas(_con_total(valor)) is None


class TestForma:
    @pytest.mark.parametrize(
        "item",
        [
            {"resumen": {}},
            {},
            {"resumen": [{"total_ofertas_recibidas": 17}]},
            {"resumen": "17"},
        ],
        ids=["clave ausente", "resumen ausente", "resumen lista", "resumen texto"],
    )
    def test_sin_resumen_utilizable_es_none(self, item):
        assert leer_total_ofertas(item) is None
