"""Credenciales de Google Calendar (HU-16).

Sin configurar, la sincronización queda apagada y el resto de la app funciona.
Con el cliente configurado a medias, la aplicación no arranca: el error
aparecería recién cuando un usuario intentara conectar su calendario.
"""

import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.config import Settings

BASE = {
    "postgres_password": "x",
    "gemini_api_key": "x",
    "gemini_model": "x",
    "mercado_publico_api_key": "x",
    "supabase_url": "http://127.0.0.1:54321",
}
LLAVE = Fernet.generate_key().decode()


def _construir(**extra) -> Settings:
    return Settings(_env_file=None, **BASE, **extra)  # type: ignore[arg-type,call-arg]


def test_por_defecto_la_sincronizacion_esta_apagada():
    settings = _construir()

    assert settings.google_calendar_enabled is False


def test_con_cliente_secreto_y_llave_queda_habilitada():
    settings = _construir(
        google_calendar_client_id="id.apps.googleusercontent.com",
        google_calendar_client_secret="secreto",
        token_encryption_key=LLAVE,
    )

    assert settings.google_calendar_enabled is True


def test_la_redireccion_apunta_al_frontend_sin_doble_barra():
    settings = _construir(app_base_url="https://proyectosya.cl/")

    assert settings.google_calendar_redirect_uri == "https://proyectosya.cl/calendario/callback/google"


@pytest.mark.parametrize(
    ("extra", "falta"),
    [
        ({"google_calendar_client_secret": "secreto", "token_encryption_key": LLAVE}, None),
        ({"token_encryption_key": LLAVE}, "GOOGLE_CALENDAR_CLIENT_SECRET"),
        ({"google_calendar_client_secret": "secreto"}, "TOKEN_ENCRYPTION_KEY"),
        ({"google_calendar_client_secret": "  ", "token_encryption_key": LLAVE}, "GOOGLE_CALENDAR_CLIENT_SECRET"),
    ],
)
def test_con_el_cliente_configurado_exige_secreto_y_llave(extra, falta):
    if falta is None:
        _construir(google_calendar_client_id="id", **extra)
        return
    with pytest.raises(ValidationError, match=falta):
        _construir(google_calendar_client_id="id", **extra)


def test_un_id_en_blanco_cuenta_como_ausente():
    assert _construir(google_calendar_client_id="   ").google_calendar_enabled is False
