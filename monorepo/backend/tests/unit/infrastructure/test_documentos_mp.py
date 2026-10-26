"""La lista oficial de anexos que trae el listado de Mercado Público.

Usa el listado real capturado el 2026-09-28 (`tests/fixtures/mp_listado_cambios.json`).
La regla que sostiene todo: **ante la duda, `None`**. Una lista a medias dejaría
marcado como retirado un anexo que sigue publicado.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from app.domain.models.tender_ingestion_dto import DocumentoOficialDTO
from app.infrastructure.services.tenders.documentos_mp import (
    documentos_desde_payload,
    documentos_por_codigo,
)

FIXTURE = Path(__file__).parents[2] / "fixtures" / "mp_listado_cambios.json"


@pytest.fixture
def items() -> dict[str, dict[str, Any]]:
    datos = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {i["estado"]["codigo"]: i for i in datos["payload"]["items"]}


class TestItemsReales:
    def test_publicada(self, items):
        assert documentos_desde_payload(items["publicada"]) == [
            DocumentoOficialDTO(
                mp_document_id=1931002,
                nombre="Anexo 3 Composición personalidad juridica.xlsx",
            ),
            DocumentoOficialDTO(
                mp_document_id=1931003, nombre="anexos (1,1-A, 2).docx"
            ),
        ]

    def test_cerrada(self, items):
        assert documentos_desde_payload(items["cerrada"]) == [
            DocumentoOficialDTO(
                mp_document_id=1927964, nombre="Especificaciones Técnicas.pdf"
            )
        ]

    def test_cancelada_trae_lista_vacia_y_no_none(self, items):
        """Sin anexos es una respuesta ([]); que falte la clave, no."""
        documentos = documentos_desde_payload(items["cancelada"])

        assert documentos is not None
        assert documentos == []


class TestLoIlegibleEsNone:
    """En todos los casos la lista entera queda en `None`, no a medias."""

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"documentos": None},
            {"documentos": "x"},
            {"documentos": ["no soy un dict"]},
            {"documentos": [{"nombre": "a.pdf"}]},
            {"documentos": [{"id": True, "nombre": "a.pdf"}]},
            {"documentos": [{"id": 0, "nombre": "a.pdf"}]},
            {"documentos": [{"id": -5, "nombre": "a.pdf"}]},
            {"documentos": [{"id": "abc", "nombre": "a.pdf"}]},
            {"documentos": [{"id": 1}]},
            {"documentos": [{"id": 1, "nombre": ""}]},
            {"documentos": [{"id": 1, "nombre": "   "}]},
            # Uno bueno y uno malo: no se devuelve la mitad.
            {"documentos": [{"id": 1, "nombre": "a.pdf"}, {"id": None, "nombre": "b"}]},
        ],
    )
    def test_devuelve_none(self, payload):
        assert documentos_desde_payload(payload) is None


class TestNormalizacion:
    def test_un_id_en_texto_con_digitos_se_convierte(self):
        documentos = documentos_desde_payload(
            {"documentos": [{"id": "123", "nombre": "a.pdf"}]}
        )

        assert documentos == [DocumentoOficialDTO(mp_document_id=123, nombre="a.pdf")]

    def test_el_nombre_se_recorta(self):
        documentos = documentos_desde_payload(
            {"documentos": [{"id": 1, "nombre": "  a.pdf "}]}
        )

        assert documentos is not None
        assert documentos[0].nombre == "a.pdf"

    def test_con_un_id_repetido_se_conserva_el_primero(self):
        """Dos filas con la misma clave en un `INSERT ... ON CONFLICT DO UPDATE`
        hacen fallar la sentencia entera."""
        documentos = documentos_desde_payload(
            {
                "documentos": [
                    {"id": 1, "nombre": "a.pdf"},
                    {"id": 1, "nombre": "b.pdf"},
                ]
            }
        )

        assert documentos == [DocumentoOficialDTO(mp_document_id=1, nombre="a.pdf")]


class TestDocumentosPorCodigo:
    def test_los_cuatro_items_del_fixture(self, items):
        por_codigo = documentos_por_codigo(items.values())

        assert set(por_codigo) == {
            "5052-431-COT26",
            "5684-369-COT26",
            "1058078-836-COT26",
            "5153-1851-COT26",
        }
        assert por_codigo["5153-1851-COT26"] == []
        assert len(por_codigo["5052-431-COT26"]) == 2

    def test_omite_los_items_sin_codigo_y_los_ilegibles(self):
        por_codigo = documentos_por_codigo(
            [
                {"documentos": [{"id": 1, "nombre": "a.pdf"}]},
                {"codigo": "ROTO", "documentos": [{"id": None, "nombre": "a.pdf"}]},
                {"codigo": "SIN-CLAVE"},
                {"codigo": "OK", "documentos": [{"id": 2, "nombre": "b.pdf"}]},
            ]
        )

        assert por_codigo == {
            "OK": [DocumentoOficialDTO(mp_document_id=2, nombre="b.pdf")]
        }
