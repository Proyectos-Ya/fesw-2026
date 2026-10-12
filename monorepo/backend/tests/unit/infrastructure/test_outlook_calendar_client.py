"""Cliente de Outlook Calendar con Microsoft identity v2 y Graph (HU-16, criterio 2)."""

import json
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import httpx
import pytest
import respx

from app.domain.entities.calendar import CalendarEventDraft
from app.domain.errors.calendar_errors import (
    CalendarAuthExpired,
    CalendarEventNotFound,
    CalendarPermissionMissing,
    CalendarProviderUnavailable,
)
from app.infrastructure.services.calendar.outlook_calendar_client import (
    OutlookCalendarClient,
)

AHORA = datetime(2026, 10, 1, 12, 0)
AUTHORIZE_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
ME_URL = "https://graph.microsoft.com/v1.0/me"
EVENTS_URL = "https://graph.microsoft.com/v1.0/me/events"
REDIRECT = "http://localhost:3000/calendario/callback/outlook"
# Microsoft devuelve los scopes de Graph con su prefijo completo.
SCOPES = (
    "https://graph.microsoft.com/Calendars.ReadWrite "
    "https://graph.microsoft.com/User.Read openid email profile"
)


@pytest.fixture
def client() -> OutlookCalendarClient:
    return OutlookCalendarClient(
        client_id="00000000-aaaa-bbbb-cccc-000000000000",
        client_secret="secreto-azure",
        redirect_uri=REDIRECT,
        tenant="common",
        now=lambda: AHORA,
    )


def _tokens(**cambios: object) -> dict[str, object]:
    datos: dict[str, object] = {
        "access_token": "eyJ.acceso",
        "refresh_token": "M.R3_refresco",
        "expires_in": 3600,
        "scope": SCOPES,
        "token_type": "Bearer",
    }
    datos.update(cambios)
    return datos


def _borrador() -> CalendarEventDraft:
    return CalendarEventDraft(
        milestone_id=UUID("11111111-1111-1111-1111-111111111111"),
        title="Visita técnica — Reparación de techumbre",
        description="Ver la licitación en Chiripa: https://app/matches/t-1",
        start=datetime(2026, 10, 20, 18, 0),  # 15:00 en Chile (UTC-3)
        end=datetime(2026, 10, 20, 19, 0),
        reminders_minutes=(1440, 60),
        return_url="https://app/matches/t-1",
    )


class TestUrlDeAutorizacion:
    def test_pide_calendarios_acceso_sin_conexion_y_correo(self, client):
        url = urlparse(client.authorization_url("estado-123"))
        params = {k: v[0] for k, v in parse_qs(url.query).items()}

        assert f"{url.scheme}://{url.netloc}{url.path}" == AUTHORIZE_URL
        assert params["client_id"] == "00000000-aaaa-bbbb-cccc-000000000000"
        assert params["redirect_uri"] == REDIRECT
        assert params["response_type"] == "code"
        assert params["response_mode"] == "query"
        scopes = params["scope"].split()
        # offline_access es lo que entrega el refresh token para sincronizar después.
        assert {"openid", "email", "offline_access", "User.Read", "Calendars.ReadWrite"} <= set(scopes)
        assert params["state"] == "estado-123"

    def test_el_tenant_configurado_va_en_la_url(self):
        cliente = OutlookCalendarClient(
            client_id="id", client_secret="s", redirect_uri=REDIRECT, tenant="consumers"
        )

        assert cliente.authorization_url("x").startswith(
            "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?"
        )


class TestIntercambioDeCodigo:
    @respx.mock
    async def test_entrega_tokens_vencimiento_y_correo(self, client):
        token = respx.post(TOKEN_URL).respond(200, json=_tokens())
        me = respx.get(ME_URL).respond(200, json={"mail": "usuario@outlook.com", "userPrincipalName": "x"})

        tokens = await client.exchange_code("codigo-microsoft")

        assert tokens.access_token == "eyJ.acceso"
        assert tokens.refresh_token == "M.R3_refresco"
        assert tokens.expires_at == AHORA + timedelta(seconds=3600)
        assert tokens.account_email == "usuario@outlook.com"
        form = parse_qs(token.calls.last.request.content.decode())
        assert form["grant_type"] == ["authorization_code"]
        assert form["code"] == ["codigo-microsoft"]
        assert form["redirect_uri"] == [REDIRECT]
        assert form["client_secret"] == ["secreto-azure"]
        assert me.calls.last.request.headers["Authorization"] == "Bearer eyJ.acceso"

    @respx.mock
    async def test_sin_mail_usa_el_nombre_principal(self, client):
        # Las cuentas personales a veces no traen `mail`.
        respx.post(TOKEN_URL).respond(200, json=_tokens())
        respx.get(ME_URL).respond(200, json={"mail": None, "userPrincipalName": "usuario@hotmail.com"})

        tokens = await client.exchange_code("codigo")

        assert tokens.account_email == "usuario@hotmail.com"

    @respx.mock
    async def test_sin_permiso_de_calendario_lo_rechaza(self, client):
        respx.post(TOKEN_URL).respond(200, json=_tokens(scope="https://graph.microsoft.com/User.Read openid"))

        with pytest.raises(CalendarPermissionMissing):
            await client.exchange_code("codigo")

    @respx.mock
    async def test_si_falla_el_correo_igual_conecta(self, client):
        respx.post(TOKEN_URL).respond(200, json=_tokens())
        respx.get(ME_URL).respond(500)

        tokens = await client.exchange_code("codigo")

        assert tokens.account_email is None

    @respx.mock
    async def test_codigo_vencido_pide_reconectar(self, client):
        respx.post(TOKEN_URL).respond(400, json={"error": "invalid_grant", "error_description": "AADSTS70008"})

        with pytest.raises(CalendarAuthExpired):
            await client.exchange_code("codigo")

    @respx.mock
    async def test_otro_error_no_registra_el_codigo(self, client, caplog):
        respx.post(TOKEN_URL).respond(500, text="error con codigo-secreto adentro")

        with caplog.at_level("DEBUG"), pytest.raises(CalendarProviderUnavailable):
            await client.exchange_code("codigo-secreto")

        assert "codigo-secreto" not in caplog.text
        assert "secreto-azure" not in caplog.text

    @respx.mock
    async def test_sin_respuesta_queda_no_disponible(self, client):
        respx.post(TOKEN_URL).mock(side_effect=httpx.ConnectTimeout("lento"))

        with pytest.raises(CalendarProviderUnavailable):
            await client.exchange_code("codigo")


class TestRefresco:
    @respx.mock
    async def test_entrega_el_refresh_token_nuevo(self, client):
        # Microsoft rota el refresh token en cada refresco: hay que guardar el nuevo.
        token = respx.post(TOKEN_URL).respond(
            200, json=_tokens(access_token="eyJ.nuevo", refresh_token="M.R3_rotado")
        )

        tokens = await client.refresh("M.R3_refresco")

        assert tokens.access_token == "eyJ.nuevo"
        assert tokens.refresh_token == "M.R3_rotado"
        form = parse_qs(token.calls.last.request.content.decode())
        assert form["grant_type"] == ["refresh_token"]
        assert form["refresh_token"] == ["M.R3_refresco"]
        assert "Calendars.ReadWrite" in form["scope"][0]

    @respx.mock
    async def test_refresh_revocado_pide_reconectar(self, client):
        respx.post(TOKEN_URL).respond(400, json={"error": "invalid_grant"})

        with pytest.raises(CalendarAuthExpired):
            await client.refresh("M.R3_revocado")


class TestRevocacion:
    async def test_no_falla_porque_microsoft_no_revoca_tokens_sueltos(self, client):
        # Microsoft identity v2 no tiene un endpoint para revocar un token. Se
        # borra la conexión local y el usuario quita el permiso en su cuenta.
        await client.revoke("M.R3_refresco")


class TestEventos:
    @respx.mock
    async def test_crea_el_evento_en_utc_con_un_recordatorio(self, client):
        ruta = respx.post(EVENTS_URL).respond(201, json={"id": "AAMk-evento"})

        evento_id = await client.create_event("eyJ.acceso", _borrador())

        assert evento_id == "AAMk-evento"
        peticion = ruta.calls.last.request
        assert peticion.headers["Authorization"] == "Bearer eyJ.acceso"
        cuerpo = json.loads(peticion.content)
        assert cuerpo["subject"] == "Visita técnica — Reparación de techumbre"
        assert cuerpo["body"] == {
            "contentType": "text",
            "content": "Ver la licitación en Chiripa: https://app/matches/t-1",
        }
        # En UTC: Outlook lo muestra en la zona del usuario.
        assert cuerpo["start"] == {"dateTime": "2026-10-20T18:00:00", "timeZone": "UTC"}
        assert cuerpo["end"] == {"dateTime": "2026-10-20T19:00:00", "timeZone": "UTC"}
        # Outlook admite un solo aviso por evento: el más anticipado.
        assert cuerpo["isReminderOn"] is True
        assert cuerpo["reminderMinutesBeforeStart"] == 1440

    @respx.mock
    async def test_un_reintento_no_duplica_el_evento(self, client):
        # Graph descarta un segundo POST con el mismo transactionId.
        ruta = respx.post(EVENTS_URL).respond(201, json={"id": "AAMk-evento"})

        await client.create_event("eyJ.acceso", _borrador())

        assert json.loads(ruta.calls.last.request.content)["transactionId"] == (
            "11111111-1111-1111-1111-111111111111"
        )

    @respx.mock
    async def test_actualiza_el_evento_existente(self, client):
        ruta = respx.patch(f"{EVENTS_URL}/AAMk%2Fevento").respond(200, json={"id": "AAMk/evento"})

        await client.update_event("eyJ.acceso", "AAMk/evento", _borrador())

        cuerpo = json.loads(ruta.calls.last.request.content)
        assert cuerpo["start"]["dateTime"] == "2026-10-20T18:00:00"
        assert "transactionId" not in cuerpo

    @respx.mock
    async def test_token_rechazado_pide_reconectar(self, client):
        respx.post(EVENTS_URL).respond(401)

        with pytest.raises(CalendarAuthExpired):
            await client.create_event("eyJ.vencido", _borrador())

    @respx.mock
    @pytest.mark.parametrize("estado", [404, 410])
    async def test_evento_borrado_por_el_usuario(self, client, estado):
        respx.patch(f"{EVENTS_URL}/AAMk-evento").respond(estado)

        with pytest.raises(CalendarEventNotFound):
            await client.update_event("eyJ.acceso", "AAMk-evento", _borrador())

    @respx.mock
    async def test_otro_error_queda_no_disponible_sin_registrar_el_token(self, client, caplog):
        respx.post(EVENTS_URL).respond(503)

        with caplog.at_level("DEBUG"), pytest.raises(CalendarProviderUnavailable):
            await client.create_event("eyJ.acceso-secreto", _borrador())

        assert "eyJ.acceso-secreto" not in caplog.text

    @respx.mock
    async def test_crear_sin_id_en_la_respuesta_queda_no_disponible(self, client):
        respx.post(EVENTS_URL).respond(201, json={})

        with pytest.raises(CalendarProviderUnavailable):
            await client.create_event("eyJ.acceso", _borrador())
