"""Configuración del procesamiento de anexos (plan 233, decisión 4)."""

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


def test_defaults_procesamiento_anexos(monkeypatch):
    monkeypatch.delenv("RUN_ATTACHMENT_PROCESSING", raising=False)
    s = _construir()
    assert s.run_attachment_processing is True
    assert s.attachment_gemini_daily_budget == 100
    assert s.gemini_extraction_model is None
    assert s.attachment_extraction_model == "x"
    assert s.attachment_processing_poll_seconds == 60
    assert s.attachment_processing_sweep_seconds == 900


def test_modelo_de_extraccion_especifico(monkeypatch):
    monkeypatch.delenv("RUN_ATTACHMENT_PROCESSING", raising=False)
    s = _construir(gemini_extraction_model="gemini-otro")
    assert s.attachment_extraction_model == "gemini-otro"

    s_vacio = _construir(gemini_extraction_model="  ")
    assert s_vacio.gemini_extraction_model is None
    assert s_vacio.attachment_extraction_model == "x"


def test_tope_diario_en_cero_es_valido(monkeypatch):
    monkeypatch.delenv("RUN_ATTACHMENT_PROCESSING", raising=False)
    s = _construir(attachment_gemini_daily_budget=0)
    assert s.attachment_gemini_daily_budget == 0


def test_tope_diario_negativo_falla(monkeypatch):
    monkeypatch.delenv("RUN_ATTACHMENT_PROCESSING", raising=False)
    with pytest.raises(ValidationError):
        _construir(attachment_gemini_daily_budget=-1)


def test_intervalos_deben_ser_positivos(monkeypatch):
    monkeypatch.delenv("RUN_ATTACHMENT_PROCESSING", raising=False)
    with pytest.raises(ValidationError):
        _construir(attachment_processing_poll_seconds=0)

    with pytest.raises(ValidationError):
        _construir(attachment_processing_sweep_seconds=0)


def test_se_leen_de_las_variables(monkeypatch):
    monkeypatch.setenv("RUN_ATTACHMENT_PROCESSING", "true")
    monkeypatch.setenv("ATTACHMENT_GEMINI_DAILY_BUDGET", "50")
    monkeypatch.setenv("GEMINI_EXTRACTION_MODEL", "gemini-custom")
    monkeypatch.setenv("ATTACHMENT_PROCESSING_POLL_SECONDS", "30")
    monkeypatch.setenv("ATTACHMENT_PROCESSING_SWEEP_SECONDS", "300")

    s = _construir()
    assert s.run_attachment_processing is True
    assert s.attachment_gemini_daily_budget == 50
    assert s.gemini_extraction_model == "gemini-custom"
    assert s.attachment_extraction_model == "gemini-custom"
    assert s.attachment_processing_poll_seconds == 30
    assert s.attachment_processing_sweep_seconds == 300
