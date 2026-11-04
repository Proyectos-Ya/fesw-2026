"""El detalle de Compra Ágil trae la entrega y los requisitos (plan #294).

Solo el detalle los informa: el listado no. Un None es "no vino".
"""

from typing import Any, cast

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


class TestEntregaDelDetalle:
    def test_el_dto_trae_la_direccion_el_plazo_y_los_flags(self):
        dto = _servicio()._parse_to_dto(
            _detalle(
                entrega={
                    "direccion_entrega": "SERVIU REGION DE AYSEN RAMON FREIRE 5",
                    "plazo_entrega_dias": 5,
                },
                flags={
                    "considera_requisitos_medioambientales": True,
                    "considera_requisitos_impacto_social_economico": False,
                },
            )
        )

        assert dto.delivery_address == "SERVIU REGION DE AYSEN RAMON FREIRE 5"
        assert dto.delivery_term_days == 5
        assert dto.requires_environmental_criteria is True
        assert dto.requires_social_impact_criteria is False

    def test_sin_entrega_ni_flags_todo_queda_en_none(self):
        dto = _servicio()._parse_to_dto(_detalle())

        assert dto.delivery_address is None
        assert dto.delivery_term_days is None
        assert dto.requires_environmental_criteria is None
        assert dto.requires_social_impact_criteria is None
