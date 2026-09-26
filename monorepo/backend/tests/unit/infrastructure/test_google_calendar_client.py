from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx

from app.domain.errors.calendar_errors import (
    CalendarAuthExpired,
    CalendarPermissionMissing,
    CalendarProviderUnavailable,
)
from app.infrastructure.services.calendar.google_calendar_client import (
    GoogleCalendarClient,
)

AHORA = datetime(2026, 10, 1, 12, 0)
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
SCOPES = "openid https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/calendar.events"
REDIRECT = "http://localhost:3000/calendario/callback/google"


@pytest.fixture
def client() -> GoogleCalendarClient:
    return GoogleCalendarClient(
        client_id="cliente.apps.googleusercontent.com",
        client_secret="secreto",
        redirect_uri=REDIRECT,
        now=lambda: AHORA,
    )


class TestUrlDeAutorizacion:
    def test_pide_calendar_events_offline_y_consentimiento(self, client):
        url = urlparse(client.authorization_url("estado-123"))
        params = {k: v[0] for k, v in parse_qs(url.query).items()}

        assert f"{url.scheme}://{url.netloc}{url.path}" == "https://accounts.google.com/o/oauth2/v2/auth"
        assert params["client_id"] == "cliente.apps.googleusercontent.com"
        assert params["redirect_uri"] == REDIRECT
        assert params["response_type"] == "code"
        assert "https://www.googleapis.com/auth/calendar.events" in params["scope"].split()
        assert "email" in params["scope"].split()
        assert params["access_type"] == "offline"
        assert params["prompt"] == "consent"
        assert params["state"] == "estado-123"

    def test_no_pide_el_calendario_completo(self, client):
        url = client.authorization_url("x")

        assert "auth%2Fcalendar+" not in url
        assert not url.endswith("auth%2Fcalendar")


class TestIntercambioDeCodigo:
    @respx.mock
    async def test_entrega_tokens_vencimiento_y_correo(self, client):
        token = respx.post(TOKEN_URL).respond(
            200,
            json={
                "access_token": "ya29.acceso",
                "refresh_token": "1//refresco",
                "expires_in": 3599,
                "scope": SCOPES,
                "token_type": "Bearer",
            },
        )
        userinfo = respx.get(USERINFO_URL).respond(200, json={"email": "usuario@gmail.com"})

        tokens = await client.exchange_code("codigo-google")

        assert tokens.access_token == "ya29.acceso"
        assert tokens.refresh_token == "1//refresco"
        assert tokens.expires_at == AHORA + timedelta(seconds=3599)
        assert tokens.account_email == "usuario@gmail.com"
        form = parse_qs(token.calls.last.request.content.decode())
        assert form["grant_type"] == ["authorization_code"]
        assert form["code"] == ["codigo-google"]
        assert form["redirect_uri"] == [REDIRECT]
        assert form["client_secret"] == ["secreto"]
        assert userinfo.calls.last.request.headers["Authorization"] == "Bearer ya29.acceso"

    @respx.mock
    async def test_si_el_usuario_no_autorizo_el_calendario_lo_rechaza(self, client):
        # Google permite desmarcar permisos en la pantalla de consentimiento.
        respx.post(TOKEN_URL).respond(
            200,
            json={"access_token": "a", "refresh_token": "r", "expires_in": 3600, "scope": "openid email"},
        )

        with pytest.raises(CalendarPermissionMissing):
            await client.exchange_code("codigo")

    @respx.mock
    async def test_si_no_se_puede_leer_el_correo_igual_conecta(self, client):
        respx.post(TOKEN_URL).respond(
            200, json={"access_token": "a", "refresh_token": "r", "expires_in": 3600, "scope": SCOPES}
        )
        respx.get(USERINFO_URL).respond(500)

        tokens = await client.exchange_code("codigo")

        assert tokens.account_email is None

    @respx.mock
    async def test_un_codigo_vencido_o_reusado_pide_reconectar(self, client):
        respx.post(TOKEN_URL).respond(400, json={"error": "invalid_grant"})

        with pytest.raises(CalendarAuthExpired):
            await client.exchange_code("codigo-viejo")

    @respx.mock
    async def test_google_caido_es_no_disponible(self, client):
        respx.post(TOKEN_URL).mock(side_effect=httpx.ConnectError("sin red"))

        with pytest.raises(CalendarProviderUnavailable):
            await client.exchange_code("codigo")


class TestRefresco:
    @respx.mock
    async def test_refresca_el_token_de_acceso(self, client):
        ruta = respx.post(TOKEN_URL).respond(200, json={"access_token": "nuevo", "expires_in": 3600})

        tokens = await client.refresh("1//refresco")

        assert tokens.access_token == "nuevo"
        assert tokens.refresh_token is None
        assert tokens.expires_at == AHORA + timedelta(hours=1)
        form = parse_qs(ruta.calls.last.request.content.decode())
        assert form["grant_type"] == ["refresh_token"]
        assert form["refresh_token"] == ["1//refresco"]

    @respx.mock
    async def test_un_refresh_token_revocado_pide_reconectar(self, client):
        respx.post(TOKEN_URL).respond(400, json={"error": "invalid_grant"})

        with pytest.raises(CalendarAuthExpired):
            await client.refresh("1//revocado")

    @respx.mock
    async def test_un_error_del_servidor_es_no_disponible(self, client):
        respx.post(TOKEN_URL).respond(503)

        with pytest.raises(CalendarProviderUnavailable):
            await client.refresh("1//refresco")


class TestRevocacion:
    @respx.mock
    async def test_revoca_el_token(self, client):
        ruta = respx.post(REVOKE_URL).respond(200)

        await client.revoke("1//refresco")

        assert parse_qs(ruta.calls.last.request.content.decode())["token"] == ["1//refresco"]

    @respx.mock
    async def test_un_fallo_al_revocar_no_interrumpe(self, client):
        respx.post(REVOKE_URL).respond(400, json={"error": "invalid_token"})

        await client.revoke("1//ya-revocado")
