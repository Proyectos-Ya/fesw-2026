from datetime import UTC, datetime, timedelta

import pytest

from app.shared.datetime_utils import (
    CHILE_TZ,
    serialize_utc,
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
