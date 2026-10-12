"""Credenciales de Outlook Calendar (HU-16, criterio 2).

Igual que Google: sin configurar, Outlook no aparece y el resto funciona; a
medias, la aplicación no arranca.
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


def test_por_defecto_outlook_esta_apagado_y_acepta_cualquier_cuenta():
    settings = _construir()

    assert settings.microsoft_calendar_enabled is False
    # `common`: cuentas personales (Outlook.com, Hotmail) y de trabajo.
    assert settings.microsoft_calendar_tenant == "common"


def test_con_cliente_secreto_y_llave_queda_habilitado():
    settings = _construir(
        microsoft_calendar_client_id="00000000-0000-0000-0000-000000000000",
        microsoft_calendar_client_secret="secreto",
        token_encryption_key=LLAVE,
    )

    assert settings.microsoft_calendar_enabled is True


def test_la_redireccion_apunta_al_frontend_sin_doble_barra():
    settings = _construir(app_base_url="https://chiripa.cl/")

    assert settings.microsoft_calendar_redirect_uri == "https://chiripa.cl/calendario/callback/outlook"


@pytest.mark.parametrize(
    ("extra", "falta"),
    [
        ({"microsoft_calendar_client_secret": "secreto", "token_encryption_key": LLAVE}, None),
        ({"token_encryption_key": LLAVE}, "MICROSOFT_CALENDAR_CLIENT_SECRET"),
        ({"microsoft_calendar_client_secret": "secreto"}, "TOKEN_ENCRYPTION_KEY"),
        ({"microsoft_calendar_client_secret": "  ", "token_encryption_key": LLAVE}, "MICROSOFT_CALENDAR_CLIENT_SECRET"),
    ],
)
def test_con_el_cliente_configurado_exige_secreto_y_llave(extra, falta):
    if falta is None:
        _construir(microsoft_calendar_client_id="id", **extra)
        return
    with pytest.raises(ValidationError, match=falta):
        _construir(microsoft_calendar_client_id="id", **extra)


def test_un_id_en_blanco_cuenta_como_ausente():
    assert _construir(microsoft_calendar_client_id="   ").microsoft_calendar_enabled is False


def test_google_y_outlook_juntos_comparten_la_llave():
    settings = _construir(
        google_calendar_client_id="id.apps.googleusercontent.com",
        google_calendar_client_secret="secreto",
        microsoft_calendar_client_id="id",
        microsoft_calendar_client_secret="secreto",
        token_encryption_key=LLAVE,
    )

    assert settings.google_calendar_enabled and settings.microsoft_calendar_enabled
