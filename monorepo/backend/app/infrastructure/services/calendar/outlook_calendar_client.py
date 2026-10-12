import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

import httpx

from app.application.services.calendar_provider_client import (
    ICalendarProviderClient,
    OAuthTokens,
)
from app.domain.entities.calendar import CalendarEventDraft
from app.domain.errors.calendar_errors import (
    CalendarAuthExpired,
    CalendarEventNotFound,
    CalendarPermissionMissing,
    CalendarProviderUnavailable,
)
from app.shared.datetime_utils import utc_now_naive

logger = logging.getLogger(__name__)

_LOGIN_URL = "https://login.microsoftonline.com"
_GRAPH_URL = "https://graph.microsoft.com/v1.0"
_EVENTS_URL = f"{_GRAPH_URL}/me/events"
# Graph no tiene un permiso más acotado que este para crear y actualizar eventos.
CALENDAR_SCOPE = "Calendars.ReadWrite"
# offline_access es lo que entrega el refresh token; User.Read, el correo de la cuenta.
_SCOPES = f"openid email offline_access User.Read {CALENDAR_SCOPE}"
_TIMEOUT_SECONDS = 15.0


class OutlookCalendarClient(ICalendarProviderClient):
    """OAuth 2.0 de Microsoft identity v2 y Microsoft Graph con httpx, sin SDK.

    Se prueba con respx igual que el cliente de Google.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        tenant: str = "common",
        now: Callable[[], datetime] = utc_now_naive,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.now = now
        self._oauth_url = f"{_LOGIN_URL}/{tenant}/oauth2/v2.0"

    def authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "response_mode": "query",
            "scope": _SCOPES,
            # Deja elegir la cuenta: muchos usuarios tienen una personal y otra de trabajo.
            "prompt": "select_account",
            "state": state,
        }
        return f"{self._oauth_url}/authorize?{urlencode(params)}"

    async def exchange_code(self, code: str) -> OAuthTokens:
        datos = await self._token(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "scope": _SCOPES,
            }
        )
        if not _concede_calendario(datos.get("scope")):
            raise CalendarPermissionMissing()
        access_token = str(datos["access_token"])
        return OAuthTokens(
            access_token=access_token,
            refresh_token=_opcional(datos.get("refresh_token")),
            expires_at=self._vencimiento(datos),
            account_email=await self._email(access_token),
        )

    async def refresh(self, refresh_token: str) -> OAuthTokens:
        # Microsoft rota el refresh token: el nuevo reemplaza al anterior.
        datos = await self._token(
            {"grant_type": "refresh_token", "refresh_token": refresh_token, "scope": _SCOPES}
        )
        return OAuthTokens(
            access_token=str(datos["access_token"]),
            refresh_token=_opcional(datos.get("refresh_token")),
            expires_at=self._vencimiento(datos),
        )

    async def revoke(self, token: str) -> None:
        # Microsoft identity v2 no tiene un endpoint para revocar un token
        # suelto (la alternativa de Graph cierra *todas* las sesiones del
        # usuario). Se borra la conexión local; el permiso se quita desde la
        # cuenta Microsoft (account.live.com/consent o myapps.microsoft.com).
        logger.info("Outlook no permite revocar el token desde la app; se borra la conexión local")

    async def create_event(self, access_token: str, draft: CalendarEventDraft) -> str:
        # transactionId: si el mismo POST se repite (reintento), Graph no crea otro evento.
        cuerpo = {**_cuerpo_evento(draft), "transactionId": str(draft.milestone_id)}
        respuesta = await self._evento("POST", _EVENTS_URL, access_token, cuerpo)
        evento_id = respuesta.json().get("id")
        if not evento_id:
            raise CalendarProviderUnavailable()
        return str(evento_id)

    async def update_event(self, access_token: str, event_id: str, draft: CalendarEventDraft) -> None:
        await self._evento(
            "PATCH", f"{_EVENTS_URL}/{quote(event_id, safe='')}", access_token, _cuerpo_evento(draft)
        )

    async def _evento(
        self, metodo: str, url: str, access_token: str, cuerpo: dict[str, object]
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as http:
                respuesta = await http.request(
                    metodo,
                    url,
                    json=cuerpo,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
        except httpx.HTTPError as error:
            raise CalendarProviderUnavailable() from error
        if respuesta.status_code in (200, 201):
            return respuesta
        if respuesta.status_code == 401:
            raise CalendarAuthExpired()
        if respuesta.status_code in (404, 410):
            raise CalendarEventNotFound()
        logger.error("Outlook Calendar rechazó el evento (HTTP %s)", respuesta.status_code)
        raise CalendarProviderUnavailable()

    async def _token(self, form: dict[str, str]) -> dict[str, object]:
        form = {**form, "client_id": self.client_id, "client_secret": self.client_secret}
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as http:
                respuesta = await http.post(f"{self._oauth_url}/token", data=form)
        except httpx.HTTPError as error:
            raise CalendarProviderUnavailable() from error

        if respuesta.status_code == 200:
            datos = respuesta.json()
            if isinstance(datos, dict) and "access_token" in datos:
                return datos
            raise CalendarProviderUnavailable()
        if respuesta.status_code in (400, 401) and _error_oauth(respuesta) == "invalid_grant":
            raise CalendarAuthExpired()
        # El cuerpo puede traer el código o el refresh token: se registra solo el estado.
        logger.error("Microsoft rechazó la petición de token (HTTP %s)", respuesta.status_code)
        raise CalendarProviderUnavailable()

    async def _email(self, access_token: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as http:
                respuesta = await http.get(
                    f"{_GRAPH_URL}/me", headers={"Authorization": f"Bearer {access_token}"}
                )
        except httpx.HTTPError:
            return None
        if respuesta.status_code != 200:
            return None
        datos = respuesta.json()
        # Las cuentas personales a veces no traen `mail`; el nombre principal sí.
        return _opcional(datos.get("mail")) or _opcional(datos.get("userPrincipalName"))

    def _vencimiento(self, datos: dict[str, object]) -> datetime:
        segundos = datos.get("expires_in", 3600)
        return self.now() + timedelta(seconds=int(segundos) if isinstance(segundos, int | str) else 3600)


def _concede_calendario(scope: object) -> bool:
    """Microsoft devuelve los scopes de Graph con su prefijo (`https://graph.microsoft.com/...`)."""
    concedidos = str(scope or "").lower().split()
    objetivo = CALENDAR_SCOPE.lower()
    return any(s == objetivo or s.endswith(f"/{objetivo}") for s in concedidos)


def _utc(fecha: datetime) -> dict[str, str]:
    """En UTC: Outlook lo muestra en la zona del usuario y no hay que traducir
    `America/Santiago` a los nombres de zona de Windows."""
    return {"dateTime": fecha.isoformat(timespec="seconds"), "timeZone": "UTC"}


def _cuerpo_evento(draft: CalendarEventDraft) -> dict[str, object]:
    return {
        "subject": draft.title,
        "body": {"contentType": "text", "content": draft.description},
        "start": _utc(draft.start),
        "end": _utc(draft.end),
        # Outlook admite un solo aviso por evento: el más anticipado.
        "isReminderOn": bool(draft.reminders_minutes),
        "reminderMinutesBeforeStart": max(draft.reminders_minutes, default=0),
    }


def _opcional(valor: object) -> str | None:
    return str(valor) if valor else None


def _error_oauth(respuesta: httpx.Response) -> str | None:
    try:
        datos = respuesta.json()
    except ValueError:
        return None
    return datos.get("error") if isinstance(datos, dict) else None
