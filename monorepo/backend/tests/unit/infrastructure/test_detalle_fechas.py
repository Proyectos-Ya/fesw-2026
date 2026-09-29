"""Las fechas del detalle se guardan en UTC leyendo la hora de Chile.

El detalle real trae `"2026-09-29 13:30"` sin zona (verificado el 2026-09-28).
Mismo parser que el listado y el cron de estados: si dos rutas leyeran distinto
la misma fecha, cada una sobrescribiría la de la otra con horas de diferencia.
"""

from typing import Any, cast

from app.infrastructure.services.tenders.tender_ingestion_service import (
    TenderIngestionService,
)
from app.shared.datetime_utils import fecha_mp_a_utc


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
