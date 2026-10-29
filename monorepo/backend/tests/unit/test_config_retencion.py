"""Los días de retención de licitaciones cerradas se ajustan por entorno (plan 306).

La API comparte esta configuración con los crons: un valor que no se pueda leer
impide que arranque. Vacío o `off` apagan el borrado en vez de romper.
"""

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


def test_por_defecto_son_7_dias():
    assert _construir().retencion_cerradas_dias == 7


def test_se_lee_de_la_variable(monkeypatch):
    monkeypatch.setenv("RETENCION_CERRADAS_DIAS", "14")

    assert _construir().retencion_cerradas_dias == 14


@pytest.mark.parametrize("valor", ["", " ", "off", "none", "NO"])
def test_vacio_u_off_apaga_el_borrado(monkeypatch, valor):
    monkeypatch.setenv("RETENCION_CERRADAS_DIAS", valor)

    assert _construir().retencion_cerradas_dias is None


@pytest.mark.parametrize("valor", ["0", "-3"])
def test_menos_de_un_dia_no_se_acepta(monkeypatch, valor):
    """Con 0 se borrarían licitaciones recién cerradas."""
    monkeypatch.setenv("RETENCION_CERRADAS_DIAS", valor)

    with pytest.raises(ValidationError):
        _construir()
