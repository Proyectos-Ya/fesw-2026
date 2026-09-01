"""El código de estado viaja como string documentado, no como número adivinado.

La API entrega `estado.codigo` —`publicada`, `cerrada`, `desierta`…— y también un
`id_estado` numérico que su guía **no documenta**. El pipeline usaba el número y
lo traducía con un mapa heredado de la API de Licitaciones, que numera distinto:
el 6 quedaba como "publicada" cuando en realidad es "desierta".

Tomar el string de origen elimina la traducción y, con ella, la posibilidad de
que el mapa vuelva a divergir de la realidad.
"""

import pytest

from app.domain.models.tender_ingestion_dto import TenderIngestaDTO

BASE = {
    "CodigoExterno": "1057539-228-COT26",
    "Nombre": "Construcción de aceras",
    "FechaPublicacion": "2026-08-01T10:00:00",
    "FechaCierre": "2026-09-01T10:00:00",
    "RutComprador": "61.000.000-0",
    "NombreOrganismo": "Municipalidad de Catemu",
    "UnidadCompra": "Dirección de Obras",
    "RegionId": 5,
    "RegionUnidad": "Valparaíso",
}


class TestCodigoDeEstado:
    def test_lleva_el_codigo_semantico_de_la_api(self):
        dto = TenderIngestaDTO.model_validate(
            {**BASE, "CodigoEstado": 2, "EstadoCodigo": "publicada"}
        )

        assert dto.status_semantic_code == "publicada"

    def test_conserva_el_id_numerico_para_la_tabla_de_estados(self):
        """`tender.status_id` sigue siendo un FK entero; el id no se descarta."""
        dto = TenderIngestaDTO.model_validate(
            {**BASE, "CodigoEstado": 6, "EstadoCodigo": "desierta"}
        )

        assert dto.status_code == 6
        assert dto.status_semantic_code == "desierta"

    def test_normaliza_mayusculas_y_espacios(self):
        dto = TenderIngestaDTO.model_validate(
            {**BASE, "CodigoEstado": 2, "EstadoCodigo": "  Publicada  "}
        )

        assert dto.status_semantic_code == "publicada"

    def test_sin_codigo_queda_en_desconocido(self):
        """Antes de que la API lo entregara siempre, o si dejara de hacerlo.

        `desconocido` no está en ACTIVE_TENDER_STATUSES, así que la licitación
        no se recomienda: ante la duda, no se afirma que esté abierta.
        """
        dto = TenderIngestaDTO.model_validate({**BASE, "CodigoEstado": 2})

        assert dto.status_semantic_code == "desconocido"

    @pytest.mark.parametrize("valor", ["", "   ", None])
    def test_un_codigo_vacio_tambien_es_desconocido(self, valor):
        dto = TenderIngestaDTO.model_validate(
            {**BASE, "CodigoEstado": 2, "EstadoCodigo": valor}
        )

        assert dto.status_semantic_code == "desconocido"
