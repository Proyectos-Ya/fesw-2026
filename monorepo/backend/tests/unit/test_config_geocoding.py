"""Geocodificación de las direcciones de entrega para el mapa (HU-22, #314).

Sin configurar queda apagada y el mapa sale vacío, sin errores. Con Nominatim
elegido y sin correo de contacto, la aplicación no arranca: su política de uso
exige identificarse, y sin eso nos bloquearían en silencio.
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


def test_por_defecto_la_geocodificacion_esta_apagada():
    assert _construir().geocoding_provider == "none"


def test_solo_acepta_los_proveedores_conocidos():
    with pytest.raises(ValidationError):
        _construir(geocoding_provider="google")


def test_nominatim_sin_correo_impide_arrancar():
    with pytest.raises(ValidationError, match="GEOCODING_CONTACT_EMAIL"):
        _construir(geocoding_provider="nominatim")


def test_correo_en_blanco_cuenta_como_ausente():
    with pytest.raises(ValidationError, match="GEOCODING_CONTACT_EMAIL"):
        _construir(geocoding_provider="nominatim", geocoding_contact_email="  ")


def test_el_lote_y_el_intervalo_tienen_valores_por_defecto_positivos():
    s = _construir()
    assert s.geocoding_batch_size > 0
    assert s.geocoding_interval_seconds > 0


def test_nominatim_usa_el_host_publico_y_se_puede_sobrescribir():
    s = _construir(geocoding_provider="nominatim", geocoding_contact_email="a@b.cl")
    assert s.geocoding_base_url == "https://nominatim.openstreetmap.org"

    otro = _construir(
        geocoding_provider="nominatim",
        geocoding_contact_email="a@b.cl",
        geocoding_base_url_override="https://nominatim.local/",
    )
    assert otro.geocoding_base_url == "https://nominatim.local"
