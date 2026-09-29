"""La ventana del cron de estados se ajusta por entorno, sin redesplegar código.

El volumen de cambios de Mercado Público varía mucho según la hora (medido el
2026-09-29: ~1.600 por hora a mediodía) y la API a veces responde lento. Poder
achicar o agrandar la ventana, el tope o el tiempo máximo desde el panel de
Railway es la forma de reaccionar sin un PR.
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


class TestValoresPorDefecto:
    def test_ventana_limite_y_tope(self):
        s = _construir()
        assert s.sync_estados_ventana_horas == 2.0
        assert s.sync_estados_limite == 9000
        assert s.sync_estados_timeout_minutos == 50.0


class TestDesdeElEntorno:
    def test_se_leen_de_las_variables(self, monkeypatch):
        monkeypatch.setenv("SYNC_ESTADOS_VENTANA_HORAS", "3.5")
        monkeypatch.setenv("SYNC_ESTADOS_LIMITE", "5000")
        monkeypatch.setenv("SYNC_ESTADOS_TIMEOUT_MINUTOS", "40")

        s = _construir()

        assert s.sync_estados_ventana_horas == 3.5
        assert s.sync_estados_limite == 5000
        assert s.sync_estados_timeout_minutos == 40.0

    @pytest.mark.parametrize(
        "variable",
        [
            "SYNC_ESTADOS_VENTANA_HORAS",
            "SYNC_ESTADOS_LIMITE",
            "SYNC_ESTADOS_TIMEOUT_MINUTOS",
        ],
    )
    def test_cero_o_negativo_se_rechaza(self, monkeypatch, variable):
        monkeypatch.setenv(variable, "0")
        with pytest.raises(ValidationError):
            _construir()
