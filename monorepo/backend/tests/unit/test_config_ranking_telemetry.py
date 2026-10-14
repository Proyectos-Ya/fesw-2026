"""Los dos settings opcionales de la telemetría del ranking (plan 233, decisión 8)."""

import pytest
from pydantic import ValidationError

from app.config import Settings

BASE = {
    "postgres_password": "x",
    "gemini_api_key": "x",
    "gemini_model": "x",
    "mercado_publico_api_key": "x",
    "supabase_url": "http://127.0.0.1:54321",
}


def _construir(**extra) -> Settings:
    return Settings(_env_file=None, **BASE, **extra)  # type: ignore[arg-type,call-arg]


def test_por_defecto_corre_cada_seis_horas():
    s = _construir()
    assert s.run_ranking_telemetry_jobs is True
    assert s.ranking_telemetry_interval_seconds == 6 * 60 * 60


def test_se_leen_de_las_variables(monkeypatch):
    monkeypatch.setenv("RUN_RANKING_TELEMETRY_JOBS", "false")
    monkeypatch.setenv("RANKING_TELEMETRY_INTERVAL_SECONDS", "600")

    s = _construir()

    assert s.run_ranking_telemetry_jobs is False
    assert s.ranking_telemetry_interval_seconds == 600


def test_el_intervalo_tiene_que_ser_positivo():
    with pytest.raises(ValidationError):
        _construir(ranking_telemetry_interval_seconds=0)
