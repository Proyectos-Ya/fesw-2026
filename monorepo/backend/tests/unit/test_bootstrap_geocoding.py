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
