import calendar
import os
import time
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.shared.datetime_utils import (
    CHILE_TZ,
    serialize_utc,
    to_utc_epoch,
    to_utc_naive,
    utc_now_naive,
)


class TestUtcNowNaive:
    def test_returns_naive_datetime(self):
        assert utc_now_naive().tzinfo is None

    def test_matches_current_utc_instant(self):
        delta = abs(utc_now_naive() - datetime.now(UTC).replace(tzinfo=None))
        assert delta < timedelta(seconds=5)


class TestToUtcNaive:
    def test_naive_input_is_interpreted_as_chile_local_time(self):
        # Mercado Público entrega "2026-07-27T17:42:00" en hora de Chile (UTC-4).
        chile_local = datetime(2026, 7, 27, 17, 42, 0)
        assert to_utc_naive(chile_local) == datetime(2026, 7, 27, 21, 42, 0)

    def test_naive_input_respects_chile_dst(self):
        # En enero Chile está en horario de verano (UTC-3).
        chile_summer = datetime(2026, 1, 15, 17, 42, 0)
        assert to_utc_naive(chile_summer) == datetime(2026, 1, 15, 20, 42, 0)

    def test_aware_input_is_converted_to_utc(self):
        aware = datetime(2026, 7, 27, 17, 42, 0, tzinfo=CHILE_TZ)
        assert to_utc_naive(aware) == datetime(2026, 7, 27, 21, 42, 0)

    def test_utc_aware_input_only_drops_tzinfo(self):
        aware = datetime(2026, 7, 27, 21, 42, 0, tzinfo=UTC)
        assert to_utc_naive(aware) == datetime(2026, 7, 27, 21, 42, 0)

    def test_result_is_always_naive(self):
        result = to_utc_naive(datetime(2026, 7, 27, 17, 42, 0))
        assert result is not None
        assert result.tzinfo is None

    def test_none_returns_none(self):
        assert to_utc_naive(None) is None


class TestSerializeUtc:
    def test_naive_datetime_is_serialized_with_z_suffix(self):
        result = serialize_utc(datetime(2026, 7, 27, 21, 42, 0))
        assert result == "2026-07-27T21:42:00Z"

    def test_aware_datetime_is_normalized_to_utc(self):
        result = serialize_utc(datetime(2026, 7, 27, 17, 42, 0, tzinfo=CHILE_TZ))
        assert result == "2026-07-27T21:42:00Z"

    def test_microseconds_are_preserved(self):
        result = serialize_utc(datetime(2026, 7, 27, 21, 42, 0, 123456))
        assert result == "2026-07-27T21:42:00.123456Z"

    @pytest.mark.parametrize("value", ["2026-07-27T21:42:00Z", "not-a-date"])
    def test_non_datetime_input_is_rejected(self, value: str):
        with pytest.raises(TypeError):
            serialize_utc(value)  # type: ignore[arg-type]


class TestToUtcEpoch:
    """`to_utc_epoch` alimenta los filtros de rango de fechas en Qdrant.

    El payload no guarda `datetime`: guarda enteros comparables. La conversión
    tiene que respetar la invariante del proyecto (naive == UTC).
    """

    def test_naive_input_is_treated_as_utc(self):
        value = datetime(2026, 7, 27, 21, 42, 0)
        assert to_utc_epoch(value) == calendar.timegm(value.timetuple())

    def test_utc_aware_input_matches_naive_equivalent(self):
        naive = datetime(2026, 7, 27, 21, 42, 0)
        assert to_utc_epoch(naive.replace(tzinfo=UTC)) == to_utc_epoch(naive)

    def test_aware_input_is_converted_from_its_own_offset(self):
        # 17:42 en Chile (UTC-4 en julio) es el mismo instante que 21:42 UTC.
        chile = datetime(2026, 7, 27, 17, 42, 0, tzinfo=CHILE_TZ)
        assert to_utc_epoch(chile) == to_utc_epoch(datetime(2026, 7, 27, 21, 42, 0))

    def test_returns_int(self):
        assert isinstance(to_utc_epoch(datetime(2026, 7, 27, 21, 42, 0)), int)

    def test_order_is_preserved(self):
        antes = datetime(2026, 6, 30, 23, 59, 0)
        despues = datetime(2026, 7, 1, 0, 1, 0)
        assert to_utc_epoch(antes) < to_utc_epoch(despues)

    def test_ignores_system_timezone(self):
        """El bug que este helper existe para evitar.

        `datetime.timestamp()` sobre un naive lo interpreta en la zona horaria
        del sistema. Con TZ=America/Santiago el resultado se corre 3 o 4 horas
        respecto de TZ=UTC, y el filtro de fechas devolvería un conjunto
        distinto según dónde corra el proceso: tu máquina o el contenedor.
        """
        if not hasattr(time, "tzset"):
            # En plataformas sin tzset (Windows), verificar consistencia directa
            value = datetime(2026, 7, 27, 21, 42, 0)
            assert to_utc_epoch(value) == int(datetime(2026, 7, 27, 21, 42, 0, tzinfo=timezone.utc).timestamp())
            return

        value = datetime(2026, 7, 27, 21, 42, 0)
        original = os.environ.get("TZ")
        try:
            resultados = []
            for tz in ("UTC", "America/Santiago"):
                os.environ["TZ"] = tz
                time.tzset()
                resultados.append(to_utc_epoch(value))
            assert resultados[0] == resultados[1]
        finally:
            if original is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = original
            time.tzset()

