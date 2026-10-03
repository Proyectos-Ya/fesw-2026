"""Las fechas del detalle se guardan en UTC leyendo la hora de Chile.

El detalle real trae `"2026-09-29 13:30"` sin zona (verificado el 2026-09-28).
Mismo parser que el listado y el cron de estados: si dos rutas leyeran distinto
la misma fecha, cada una sobrescribiría la de la otra con horas de diferencia.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pytest

from app.infrastructure.services.tenders.tender_ingestion_service import (
    TenderIngestionService,
)
from app.shared.datetime_utils import fecha_mp_a_utc

FIXTURE = Path(__file__).parents[2] / "fixtures" / "mp_listado_cambios.json"


@pytest.fixture
def items() -> dict[str, dict[str, Any]]:
    datos = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {i["estado"]["codigo"]: i for i in datos["payload"]["items"]}


def _servicio() -> TenderIngestionService:
    # `_parse_to_dto` no usa ninguna dependencia: basta con construirlo.
    return TenderIngestionService(
        engine=cast(Any, None),
        client=cast(Any, None),
        embedding_service=cast(Any, None),
    )


def _detalle(fechas: dict[str, str]) -> dict[str, Any]:
    return {
        "codigo": "5052-431-COT26",
        "nombre": "Servicio",
        "descripcion": "Descripción",
        "estado": {"id_estado": 2, "codigo": "publicada"},
        "fechas": fechas,
        "institucion": {
            "rut": "61.606.901-2",
            "organismo_comprador": "Hospital",
            "unidad_compra": "Generales",
            "region": 7,
            "nombre_region": "Región del Maule ",
        },
        "presupuesto": {"monto_disponible_clp": 49980},
        "productos_solicitados": [],
    }


class TestFechasDelDetalle:
    def test_el_formato_real_queda_en_utc(self):
        dto = _servicio()._parse_to_dto(
            _detalle(
                {
                    "fecha_publicacion": "2026-09-28 13:19",
                    "fecha_cierre": "2026-09-29 13:30",
                }
            )
        )
        assert dto.published_at == fecha_mp_a_utc("2026-09-28 13:19")
        assert dto.closing_at == fecha_mp_a_utc("2026-09-29 13:30")

    def test_con_z_coincide_con_lo_que_lee_el_listado(self):
        dto = _servicio()._parse_to_dto(
            _detalle(
                {
                    "fecha_publicacion": "2026-09-28T13:19:00Z",
                    "fecha_cierre": "2026-09-29T13:30:00Z",
                }
            )
        )
        assert dto.closing_at == fecha_mp_a_utc("2026-09-29 13:30")


class TestLlamadoDelDetalle:
    """El detalle lee el llamado con el mismo lector que el listado.

    Que `/v2/compra-agil/{code}` traiga `convocatoria` y los cierres por llamado
    no está verificado (plan 233, fase 0): si faltan, quedan en `None`.
    """

    def test_el_detalle_en_segundo_llamado_trae_llamado_y_ambos_cierres(self, items):
        # Un ítem del listado sirve: `_parse_to_dto` lee con `.get` y valores
        # por defecto.
        dto = _servicio()._parse_to_dto(items["desierta"])

        assert dto.call_number == 2
        assert dto.first_call_closing_at == datetime(2026, 9, 26, 20, 10)
        assert dto.second_call_closing_at == datetime(2026, 9, 27, 20, 28)
        assert dto.closing_at == dto.second_call_closing_at

    def test_un_detalle_sin_convocatoria_deja_el_llamado_en_none(self):
        dto = _servicio()._parse_to_dto(
            _detalle(
                {
                    "fecha_publicacion": "2026-09-28 13:19",
                    "fecha_cierre": "2026-09-29 13:30",
                }
            )
        )

        assert dto.call_number is None
        assert dto.first_call_closing_at is None
        assert dto.second_call_closing_at is None
        assert dto.closing_at == fecha_mp_a_utc("2026-09-29 13:30")
