"""Un detalle real de Compra Ágil pasa entero por `_parse_to_dto` (#294).

`tests/fixtures/mp_detalle_compra_agil.json` es la respuesta de
`GET /v2/compra-agil/1224953-521-COT26`, capturada el 2026-10-26. Confirma lo
que la guía de la API solo documentaba: el detalle trae `entrega`, `flags`,
`resumen.total_ofertas_recibidas` y `documentos`. Los cierres por llamado
vienen en `convocatoria`, no en `fechas` como en el listado.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pytest

from app.infrastructure.services.tenders.tender_ingestion_service import (
    TenderIngestionService,
)

FIXTURE = Path(__file__).parents[2] / "fixtures" / "mp_detalle_compra_agil.json"


@pytest.fixture
def dto():
    detalle = json.loads(FIXTURE.read_text(encoding="utf-8"))["payload"]
    servicio = TenderIngestionService(
        engine=cast(Any, None),
        client=cast(Any, None),
        embedding_service=cast(Any, None),
    )
    return servicio._parse_to_dto(detalle)


def test_trae_la_entrega_y_los_requisitos(dto):
    assert dto.delivery_address == "Yerbas Buenas #915"
    assert dto.delivery_term_days == 2
    assert dto.requires_environmental_criteria is False
    assert dto.requires_social_impact_criteria is False


def test_trae_las_cotizaciones_y_los_documentos(dto):
    assert dto.received_offers_count == 0
    assert [d.nombre for d in dto.documentos or []] == [
        "ET CABLE DE ALIMENTACIÓN AUTOCLAVE .pdf"
    ]


def test_trae_el_llamado_y_el_cierre_de_cada_llamado(dto):
    """En hora de Chile "2026-10-27 11:00"; el DTO guarda UTC (Chile está en UTC-3)."""
    assert dto.call_number == 1
    assert dto.first_call_closing_at == datetime(2026, 10, 27, 14, 0)
    assert dto.second_call_closing_at == datetime(2026, 10, 28, 14, 5)
