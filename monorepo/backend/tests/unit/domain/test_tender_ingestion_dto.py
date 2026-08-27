from datetime import datetime

from app.domain.models.tender_ingestion_dto import TenderIngestaDTO

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
