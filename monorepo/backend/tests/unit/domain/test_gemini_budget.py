"""Tests del cálculo de tope diario y reanudación de Gemini (plan 233, decisión 4)."""

from datetime import date, datetime

import pytest

from app.domain.services.gemini_budget import dia_del_tope, reanudar_tope_en

CASOS = [
    # (Ahora UTC, Día Chile, Inicio día siguiente UTC)
    (datetime(2026, 10, 3, 15, 0), date(2026, 10, 3), datetime(2026, 10, 4, 3, 0)),
    (datetime(2026, 10, 4, 2, 59), date(2026, 10, 3), datetime(2026, 10, 4, 3, 0)),
    (datetime(2026, 10, 4, 3, 0), date(2026, 10, 4), datetime(2026, 10, 5, 3, 0)),
    (datetime(2026, 9, 6, 3, 30), date(2026, 9, 5), datetime(2026, 9, 6, 4, 0)),
    (datetime(2027, 4, 4, 3, 30), date(2027, 4, 3), datetime(2027, 4, 4, 4, 0)),
]


@pytest.mark.parametrize("ahora_utc,dia_esperado,reanudacion_esperada", CASOS)
def test_dia_del_tope_y_reanudacion(ahora_utc, dia_esperado, reanudacion_esperada):
    assert dia_del_tope(ahora_utc) == dia_esperado
    assert reanudar_tope_en(ahora_utc) == reanudacion_esperada
