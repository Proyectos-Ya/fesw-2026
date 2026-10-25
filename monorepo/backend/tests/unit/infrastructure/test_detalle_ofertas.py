"""El detalle de Compra Ágil trae `resumen.total_ofertas_recibidas`.

Se lee con el mismo lector que el listado (`leer_total_ofertas`): si cada ruta
leyera distinto, una sobrescribiría a la otra en cada pasada.
"""

from typing import Any, cast

import pytest

from app.infrastructure.services.tenders.tender_ingestion_service import (
    TenderIngestionService,
)


def _servicio() -> TenderIngestionService:
    # `_parse_to_dto` no usa ninguna dependencia: basta con construirlo.
    return TenderIngestionService(
        engine=cast(Any, None),
        client=cast(Any, None),
        embedding_service=cast(Any, None),
    )


def _detalle(**extra: Any) -> dict[str, Any]:
    return {
        "codigo": "5052-431-COT26",
        "nombre": "Servicio",
        "descripcion": "Descripción",
        "estado": {"id_estado": 2, "codigo": "publicada"},
        "fechas": {
            "fecha_publicacion": "2026-09-28 10:00",
            "fecha_cierre": "2026-09-29 13:30",
        },
        "institucion": {
            "rut": "61.606.901-2",
            "organismo_comprador": "Hospital",
            "unidad_compra": "Generales",
            "region": 7,
            "nombre_region": "Región del Maule ",
        },
        "presupuesto": {"monto_disponible_clp": 49980},
        "productos_solicitados": [],
        **extra,
    }


class TestCotizacionesDelDetalle:
    @pytest.mark.parametrize(
        "extra, esperado",
        [
            ({"resumen": {"total_ofertas_recibidas": 4}}, 4),
            ({"resumen": {"total_ofertas_recibidas": 0}}, 0),
            ({}, None),
            ({"resumen": {"total_ofertas_recibidas": None}}, None),
        ],
        ids=["cuatro", "cero", "sin resumen", "nulo"],
    )
    def test_el_dto_trae_la_cifra_o_none(self, extra, esperado):
        dto = _servicio()._parse_to_dto(_detalle(**extra))

        assert dto.received_offers_count == esperado
