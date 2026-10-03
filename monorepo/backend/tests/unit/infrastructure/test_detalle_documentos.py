"""El detalle de una licitación puede traer la lista oficial de anexos, o no.

Hasta ahora solo está confirmado que viene en el **listado** (plan 233, fase 0).
Por eso el detalle sin `documentos` —la forma de todos los fixtures actuales— deja
`dto.documentos` en `None` ("no informa", no se toca la lista guardada) y no en
`[]` ("no hay anexos", se retiran los que había): leer la ausencia como vacío
haría que cada pasada de la ingesta borrara lo que el listado acaba de registrar.
"""

from typing import Any, cast

from app.domain.models.tender_ingestion_dto import DocumentoOficialDTO
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


def _detalle() -> dict[str, Any]:
    return {
        "codigo": "5052-431-COT26",
        "nombre": "Servicio",
        "descripcion": "Descripción",
        "estado": {"id_estado": 2, "codigo": "publicada"},
        "fechas": {
            "fecha_publicacion": "2026-09-28 13:19",
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
    }


class TestDocumentosDelDetalle:
    def test_sin_la_clave_queda_en_none_y_el_resto_se_parsea_igual(self):
        dto = _servicio()._parse_to_dto(_detalle())

        assert dto.documentos is None
        assert dto.code == "5052-431-COT26"
        assert dto.available_amount_clp == 49980

    def test_con_documentos_los_lee(self):
        detalle = {**_detalle(), "documentos": [{"id": 7, "nombre": "Bases.pdf"}]}

        dto = _servicio()._parse_to_dto(detalle)

        assert dto.documentos == [
            DocumentoOficialDTO(mp_document_id=7, nombre="Bases.pdf")
        ]

    def test_con_documentos_ilegibles_queda_en_none_sin_excepcion(self):
        detalle = {**_detalle(), "documentos": [{"id": None, "nombre": "Bases.pdf"}]}

        dto = _servicio()._parse_to_dto(detalle)

        assert dto.documentos is None
