"""El llamado vigente y el cierre de cada llamado se leen igual en el listado y en el detalle."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from app.infrastructure.services.tenders.llamados import leer_llamado

FIXTURE = Path(__file__).parents[2] / "fixtures" / "mp_listado_cambios.json"


@pytest.fixture
def items() -> dict[str, dict[str, Any]]:
    datos = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {i["estado"]["codigo"]: i for i in datos["payload"]["items"]}


class TestItemsReales:
    def test_publicada_en_primer_llamado(self, items):
        llamado = leer_llamado(items["publicada"])
        assert llamado.numero == 1
        # Hora de Chile sin convertir: la "Z" no es UTC.
        assert llamado.cierre_primer_llamado == datetime(2026, 9, 29, 13, 30)
        assert llamado.cierre_segundo_llamado == datetime(2026, 9, 30, 13, 40)

    def test_desierta_en_segundo_llamado_se_trunca_al_minuto(self, items):
        llamado = leer_llamado(items["desierta"])
        assert llamado.numero == 2
        assert llamado.cierre_primer_llamado == datetime(2026, 9, 26, 17, 10)
        # "…17:28:48.093Z" queda en 17:28, igual que `fecha_cierre`.
        assert llamado.cierre_segundo_llamado == datetime(2026, 9, 27, 17, 28)


class TestAnteLaDudaNone:
    @pytest.mark.parametrize("valor", [None, 0, 3, "2", True, 1.0])
    def test_un_numero_de_llamado_raro_no_se_inventa(self, valor):
        assert leer_llamado({"convocatoria": {"estado_convocatoria": valor}}).numero is None

    def test_sin_convocatoria_ni_fechas(self):
        llamado = leer_llamado({})
        assert (
            llamado.numero,
            llamado.cierre_primer_llamado,
            llamado.cierre_segundo_llamado,
        ) == (None, None, None)

    def test_convocatoria_que_no_es_objeto(self):
        assert leer_llamado({"convocatoria": "Segundo llamado"}).numero is None

    def test_cierre_ilegible(self):
        item = {"fechas": {"fecha_cierre_segundo_llamado": "no es fecha"}}
        assert leer_llamado(item).cierre_segundo_llamado is None

    def test_cierre_que_no_es_texto_no_revienta(self):
        item = {"fechas": {"fecha_cierre_primer_llamado": 1727630000}}
        assert leer_llamado(item).cierre_primer_llamado is None

    def test_fechas_que_no_son_objeto(self):
        assert leer_llamado({"fechas": None}).cierre_primer_llamado is None
