"""El proveedor de geocodificación se elige por configuración (HU-22, #314)."""

from app.bootstrap.builders import build_geocoding_service
from app.config import settings
from app.infrastructure.services.geocoding.nominatim_geocoding_service import (
    NominatimGeocodingService,
)


def test_sin_proveedor_la_geocodificacion_queda_apagada(monkeypatch):
    monkeypatch.setattr(settings, "geocoding_provider", "none")

    assert build_geocoding_service() is None


def test_construye_nominatim(monkeypatch):
    monkeypatch.setattr(settings, "geocoding_provider", "nominatim")
    monkeypatch.setattr(settings, "geocoding_contact_email", "a@b.cl")

    assert isinstance(build_geocoding_service(), NominatimGeocodingService)


def test_el_runner_arma_el_throttle_con_el_ritmo_configurado(monkeypatch):
    """Sin esto el throttle se queda con su default y sale a 1 por segundo."""
    from types import SimpleNamespace

    from app.bootstrap import runners

    monkeypatch.setattr(settings, "geocoding_min_interval_seconds", 15.0)
    capturado: dict[str, float] = {}

    class ThrottleEspia(runners.ThrottledGeocodingService):
        def __init__(self, inner, min_interval_seconds=1.0, **extra):
            capturado["intervalo"] = min_interval_seconds
            super().__init__(inner, min_interval_seconds, **extra)

    monkeypatch.setattr(runners, "ThrottledGeocodingService", ThrottleEspia)
    app = SimpleNamespace(state=SimpleNamespace(geocoding_service=object()))

    runners.build_geocoding_runner(app)

    assert capturado["intervalo"] == 15.0
