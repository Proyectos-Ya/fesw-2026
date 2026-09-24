from datetime import datetime

import pytest

from app.domain.errors.milestone_errors import InvalidMilestoneDate
from app.domain.services.milestone_date_normalizer import normalize_milestone_date


class TestFechaConHora:
    def test_hora_de_chile_en_horario_de_verano_se_guarda_en_utc(self):
        # "a las 15:00 del día 20" de octubre: Chile está en UTC-3.
        resultado = normalize_milestone_date("2026-10-20", "15:00")

        assert resultado.due_at == datetime(2026, 10, 20, 18, 0)
        assert resultado.has_time is True

    def test_hora_de_chile_en_horario_de_invierno_se_guarda_en_utc(self):
        # En junio Chile está en UTC-4.
        resultado = normalize_milestone_date("2026-06-20", "15:00")

        assert resultado.due_at == datetime(2026, 6, 20, 19, 0)
        assert resultado.has_time is True

    def test_acepta_segundos_en_la_hora(self):
        resultado = normalize_milestone_date("2026-10-20", "15:00:00")

        assert resultado.due_at == datetime(2026, 10, 20, 18, 0)

    def test_el_resultado_es_naive(self):
        resultado = normalize_milestone_date("2026-10-20", "15:00")

        assert resultado.due_at.tzinfo is None


class TestFechaSinHora:
    @pytest.mark.parametrize("hora", [None, "", "   "])
    def test_sin_hora_queda_marcado_y_a_medianoche_de_chile(self, hora: str | None):
        resultado = normalize_milestone_date("2026-10-20", hora)

        assert resultado.has_time is False
        assert resultado.due_at == datetime(2026, 10, 20, 3, 0)

    def test_medianoche_inexistente_por_cambio_de_hora_no_cambia_el_dia(self):
        # El 6-sep-2026 Chile adelanta el reloj a las 00:00: esa medianoche no existe.
        resultado = normalize_milestone_date("2026-09-06", None)

        assert resultado.has_time is False
        assert resultado.due_at == datetime(2026, 9, 6, 4, 0)


class TestFechasInvalidas:
    @pytest.mark.parametrize(
        "fecha",
        [
            "2026-02-30",  # día imposible
            "20/10/2026",  # formato local, no ISO
            "20261020",  # ISO básico: fromisoformat lo aceptaría
            "2026-10-20T15:00",  # la hora viaja aparte
            "",
            "el día 20",
        ],
    )
    def test_rechaza_fechas_que_no_son_iso_estrictas(self, fecha: str):
        with pytest.raises(InvalidMilestoneDate):
            normalize_milestone_date(fecha, None)

    @pytest.mark.parametrize("hora", ["25:00", "15h", "3 PM", "15:60", "a las 15"])
    def test_rechaza_horas_invalidas(self, hora: str):
        with pytest.raises(InvalidMilestoneDate):
            normalize_milestone_date("2026-10-20", hora)

    @pytest.mark.parametrize("fecha", ["1999-12-31", "2101-01-01"])
    def test_rechaza_anios_fuera_de_rango(self, fecha: str):
        with pytest.raises(InvalidMilestoneDate):
            normalize_milestone_date(fecha, None)

    def test_el_error_explica_el_motivo(self):
        with pytest.raises(InvalidMilestoneDate, match="2026-02-30"):
            normalize_milestone_date("2026-02-30", None)
