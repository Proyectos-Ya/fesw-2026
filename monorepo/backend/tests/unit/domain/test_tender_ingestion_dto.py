from datetime import datetime

import pytest
from pydantic import ValidationError

from app.domain.models.tender_ingestion_dto import (
    DocumentoOficialDTO,
    TenderIngestaDTO,
)

DateInput = str | datetime


def _build_dto(published: DateInput, closing: DateInput) -> TenderIngestaDTO:
    return TenderIngestaDTO(
        CodigoExterno="1234-56-COT26",
        Nombre="Compra ágil de prueba",
        Descripcion=None,
        CodigoEstado=5,
        # El DTO declara datetime, pero estos tests verifican justamente la
        # coerción que hace Pydantic sobre las fechas en string de la API.
        FechaPublicacion=published,  # type: ignore[arg-type]
        FechaCierre=closing,  # type: ignore[arg-type]
        RutComprador="60.000.000-0",
        NombreOrganismo="Municipalidad de Prueba",
        UnidadCompra="Unidad de Prueba",
        RegionId=13,
        RegionUnidad="Región Metropolitana",
        MontoEstimado=1000.0,
    )


class TestTenderIngestaDTONormalizesDatesToUtc:
    def test_naive_string_from_mercado_publico_is_read_as_chile_time(self):
        # La API entrega hora local de Chile sin offset; en julio es UTC-4.
        dto = _build_dto("2026-07-27T17:42:00", "2026-07-30T15:00:00")

        assert dto.published_at == datetime(2026, 7, 27, 21, 42, 0)
        assert dto.closing_at == datetime(2026, 7, 30, 19, 0, 0)

    def test_stored_dates_are_naive(self):
        dto = _build_dto("2026-07-27T17:42:00", "2026-07-30T15:00:00")

        assert dto.published_at.tzinfo is None
        assert dto.closing_at.tzinfo is None

    def test_string_with_explicit_offset_is_converted_from_that_offset(self):
        dto = _build_dto("2026-07-27T17:42:00-04:00", "2026-07-30T15:00:00Z")

        assert dto.published_at == datetime(2026, 7, 27, 21, 42, 0)
        assert dto.closing_at == datetime(2026, 7, 30, 15, 0, 0)

    def test_naive_date_in_chilean_summer_uses_dst_offset(self):
        # En enero Chile está en UTC-3.
        dto = _build_dto("2026-01-15T17:42:00", "2026-01-20T15:00:00")

        assert dto.published_at == datetime(2026, 1, 15, 20, 42, 0)
        assert dto.closing_at == datetime(2026, 1, 20, 18, 0, 0)

    def test_datetime_object_input_is_also_normalized(self):
        dto = _build_dto(
            datetime(2026, 7, 27, 17, 42, 0), datetime(2026, 7, 30, 15, 0, 0)
        )

        assert dto.published_at == datetime(2026, 7, 27, 21, 42, 0)
        assert dto.closing_at == datetime(2026, 7, 30, 19, 0, 0)


class TestTenderIngestaDTORegion:
    """El id de región viaja como dato, no se deduce del nombre.

    Mercado Público entrega `institucion.region` como entero. Deducirlo del
    nombre obligaba a mantener una tabla de alias de strings con acentos y
    variantes, y a inventar un valor por defecto cuando ninguno calzaba.
    """

    def test_conserva_el_id_de_region(self):
        dto = _build_dto("2026-07-27T17:42:00", "2026-07-30T15:00:00")

        assert dto.region_id == 13

    def test_conserva_el_nombre_de_region_para_mostrar(self):
        dto = _build_dto("2026-07-27T17:42:00", "2026-07-30T15:00:00")

        assert dto.region_name == "Región Metropolitana"

    def test_el_id_es_independiente_del_nombre(self):
        """Un nombre con otra grafía no cambia el id: ya no se deduce del texto."""
        dto = TenderIngestaDTO(
            CodigoExterno="1234-56-COT26",
            Nombre="Compra ágil de prueba",
            Descripcion=None,
            CodigoEstado=5,
            FechaPublicacion=datetime(2026, 7, 27, 17, 42, 0),
            FechaCierre=datetime(2026, 7, 30, 15, 0, 0),
            RutComprador="60.000.000-0",
            NombreOrganismo="Municipalidad de Prueba",
            UnidadCompra="Unidad de Prueba",
            RegionId=16,
            RegionUnidad="Región del Ñuble  ",  # con espacios, como los manda la API
            MontoEstimado=1000.0,
        )

        assert dto.region_id == 16


class TestDocumentosOficiales:
    """La lista oficial de anexos que publica Mercado Público.

    `None` y `[]` significan cosas distintas, y la diferencia importa: `None` es
    "la fuente no informa los anexos" (la lista guardada no se toca) y `[]` es
    "Mercado Público dice que no hay" (se retiran los que había).
    """

    def test_el_nombre_se_recorta(self):
        doc = DocumentoOficialDTO(mp_document_id=1, nombre=" Bases.pdf ")

        assert doc.nombre == "Bases.pdf"

    @pytest.mark.parametrize("id_invalido", [0, -1])
    def test_el_id_tiene_que_ser_positivo(self, id_invalido):
        with pytest.raises(ValidationError):
            DocumentoOficialDTO(mp_document_id=id_invalido, nombre="Bases.pdf")

    def test_el_nombre_no_puede_quedar_vacio(self):
        with pytest.raises(ValidationError):
            DocumentoOficialDTO(mp_document_id=1, nombre="   ")

    def test_es_inmutable(self):
        doc = DocumentoOficialDTO(mp_document_id=1, nombre="Bases.pdf")

        with pytest.raises(ValidationError):
            doc.nombre = "x"  # type: ignore[misc]

    def test_es_hashable_y_se_compara_por_valor(self):
        a = DocumentoOficialDTO(mp_document_id=1, nombre="Bases.pdf")
        b = DocumentoOficialDTO(mp_document_id=1, nombre="Bases.pdf")

        assert hash(a) == hash(b)
        assert a == b
        assert len({a, b}) == 1

    def test_sin_la_clave_la_lista_es_none_y_no_vacia(self):
        dto = _build_dto("2026-07-27T17:42:00", "2026-07-30T15:00:00")

        assert dto.documentos is None

    def test_conserva_la_lista_que_se_le_pasa(self):
        documentos = [DocumentoOficialDTO(mp_document_id=7, nombre="Bases.pdf")]
        # No se reconstruye con `model_dump(by_alias=True)`: las fechas del DTO
        # ya están en UTC y se correrían otra vez.
        dto = TenderIngestaDTO(
            CodigoExterno="1234-56-COT26",
            Nombre="Compra ágil de prueba",
            Descripcion=None,
            CodigoEstado=5,
            FechaPublicacion=datetime(2026, 7, 27, 17, 42, 0),
            FechaCierre=datetime(2026, 7, 30, 15, 0, 0),
            RutComprador="60.000.000-0",
            NombreOrganismo="Municipalidad de Prueba",
            UnidadCompra="Unidad de Prueba",
            RegionId=13,
            RegionUnidad="Región Metropolitana",
            MontoEstimado=1000.0,
            documentos=documentos,
        )

        assert dto.documentos == documentos

    def test_una_lista_vacia_se_conserva_vacia(self):
        dto = TenderIngestaDTO(
            CodigoExterno="1234-56-COT26",
            Nombre="Compra ágil de prueba",
            Descripcion=None,
            CodigoEstado=5,
            FechaPublicacion=datetime(2026, 7, 27, 17, 42, 0),
            FechaCierre=datetime(2026, 7, 30, 15, 0, 0),
            RutComprador="60.000.000-0",
            NombreOrganismo="Municipalidad de Prueba",
            UnidadCompra="Unidad de Prueba",
            RegionId=13,
            RegionUnidad="Región Metropolitana",
            MontoEstimado=1000.0,
            documentos=[],
        )

        assert dto.documentos == []


def _con_llamado(**extra: object) -> TenderIngestaDTO:
    """DTO con los campos del llamado.

    No sirve `model_copy`: no valida, así que se saltaría la normalización a UTC
    que justamente se quiere comprobar.
    """
    return TenderIngestaDTO(
        CodigoExterno="1234-56-COT26",
        Nombre="Compra ágil de prueba",
        Descripcion=None,
        CodigoEstado=5,
        FechaPublicacion=datetime(2026, 9, 25, 16, 51),
        FechaCierre=datetime(2026, 9, 27, 17, 28),
        RutComprador="60.000.000-0",
        NombreOrganismo="Municipalidad de Prueba",
        UnidadCompra="Unidad de Prueba",
        RegionId=13,
        RegionUnidad="Región Metropolitana",
        MontoEstimado=1000.0,
        **extra,  # type: ignore[arg-type]
    )


class TestLlamado:
    """Segundo llamado (plan 233, decisión 3): `closing_at` no cambia de sentido."""

    def test_los_campos_del_llamado_son_opcionales(self):
        dto = _build_dto("2026-07-27T17:42:00", "2026-07-30T15:00:00")

        assert dto.call_number is None
        assert dto.first_call_closing_at is None
        assert dto.second_call_closing_at is None

    def test_los_cierres_por_llamado_se_normalizan_a_utc(self):
        # Chile está en UTC-3 entre el 26 y el 27 de septiembre de 2026.
        dto = _con_llamado(
            NumeroLlamado=2,
            FechaCierrePrimerLlamado=datetime(2026, 9, 26, 17, 10),
            FechaCierreSegundoLlamado=datetime(2026, 9, 27, 17, 28),
        )

        assert dto.call_number == 2
        assert dto.first_call_closing_at == datetime(2026, 9, 26, 20, 10)
        assert dto.second_call_closing_at == datetime(2026, 9, 27, 20, 28)

    def test_los_cierres_por_llamado_quedan_naive(self):
        dto = _con_llamado(
            FechaCierrePrimerLlamado=datetime(2026, 9, 26, 17, 10),
            FechaCierreSegundoLlamado=datetime(2026, 9, 27, 17, 28),
        )

        assert dto.first_call_closing_at is not None
        assert dto.first_call_closing_at.tzinfo is None
        assert dto.second_call_closing_at is not None
        assert dto.second_call_closing_at.tzinfo is None

    def test_un_cierre_none_sigue_siendo_none(self):
        dto = _con_llamado(NumeroLlamado=1, FechaCierrePrimerLlamado=None)

        assert dto.first_call_closing_at is None
