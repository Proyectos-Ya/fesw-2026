"""Un ítem del listado de cambios se convierte en un cambio de estado.

Usa el listado real capturado el 2026-09-28 (`tests/fixtures/mp_listado_cambios.json`):
una publicada, una cerrada, una desierta en segundo llamado y una cancelada.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from app.infrastructure.services.tenders.listado_cambios import cambio_desde_item
from app.shared.datetime_utils import fecha_mp_a_utc

FIXTURE = Path(__file__).parents[2] / "fixtures" / "mp_listado_cambios.json"


@pytest.fixture
def items() -> dict[str, dict[str, Any]]:
    datos = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {i["estado"]["codigo"]: i for i in datos["payload"]["items"]}


class TestItemsReales:
    def test_publicada(self, items):
        cambio = cambio_desde_item(items["publicada"])
        assert cambio is not None
        assert cambio.code == "5052-431-COT26"
        assert cambio.status_id == 2
        assert cambio.status_code == "publicada"
        # "2026-09-29 13:30" en Chile (UTC-3) son las 16:30 UTC.
        assert cambio.closing_at == datetime(2026, 9, 29, 16, 30)

    def test_la_z_del_ultimo_cambio_se_lee_en_hora_de_chile(self, items):
        cambio = cambio_desde_item(items["publicada"])
        assert cambio is not None
        # "2026-09-28T13:20:00.353Z" es hora de Chile: 16:20 UTC, no 13:20.
        assert cambio.changed_at == fecha_mp_a_utc("2026-09-28 13:20:00.353")

    @pytest.mark.parametrize(
        ("codigo", "status_id"),
        [("cerrada", 3), ("desierta", 6), ("cancelada", 5)],
    )
    def test_estados_no_activos(self, items, codigo, status_id):
        cambio = cambio_desde_item(items[codigo])
        assert cambio is not None
        assert cambio.status_id == status_id
        assert cambio.status_code == codigo

    def test_la_desierta_en_segundo_llamado_trae_el_cierre_vigente(self, items):
        """`fecha_cierre` sigue al llamado vigente, no al primero."""
        cambio = cambio_desde_item(items["desierta"])
        assert cambio is not None
        assert cambio.closing_at == fecha_mp_a_utc("2026-09-27 17:28")


class TestItemsIncompletos:
    """Lo que no se puede leer se ignora: escribir un estado inventado es peor."""

    def _item(self, **cambios: Any) -> dict[str, Any]:
        base: dict[str, Any] = {
            "codigo": "X-1",
            "estado": {"id_estado": 2, "codigo": "publicada"},
            "fechas": {
                "fecha_cierre": "2026-09-29 13:30",
                "fecha_ultimo_cambio": "2026-09-28T13:20:00Z",
            },
        }
        base.update(cambios)
        return base

    def test_sin_codigo(self):
        assert cambio_desde_item(self._item(codigo=None)) is None

    def test_sin_estado(self):
        assert cambio_desde_item(self._item(estado=None)) is None
        assert cambio_desde_item(self._item(estado={"codigo": "publicada"})) is None
        assert cambio_desde_item(self._item(estado={"id_estado": 2})) is None

    def test_sin_fecha_de_cierre_legible(self):
        item = self._item(fechas={"fecha_cierre": "no es fecha"})
        assert cambio_desde_item(item) is None

    def test_sin_ultimo_cambio_igual_sirve(self):
        cambio = cambio_desde_item(
            self._item(fechas={"fecha_cierre": "2026-09-29 13:30"})
        )
        assert cambio is not None
        assert cambio.changed_at is None

    def test_el_codigo_de_estado_se_normaliza(self):
        cambio = cambio_desde_item(
            self._item(estado={"id_estado": 2, "codigo": " Publicada "})
        )
        assert cambio is not None
        assert cambio.status_code == "publicada"
