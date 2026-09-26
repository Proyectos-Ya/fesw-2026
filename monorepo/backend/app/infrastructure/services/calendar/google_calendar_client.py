import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
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
from app.shared.datetime_utils import CHILE_TZ, utc_now_naive

logger = logging.getLogger(__name__)

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
# Solo eventos: el scope completo de calendario permitiría leer y borrar todo.
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events"
_SCOPES = f"openid email {CALENDAR_SCOPE}"
_TIMEOUT_SECONDS = 15.0


class GoogleCalendarClient(ICalendarProviderClient):
    """OAuth 2.0 de Google con httpx, sin SDK: se prueba con respx igual que Gemini."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        now: Callable[[], datetime] = utc_now_naive,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.now = now

    def authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": _SCOPES,
            # offline + consent: Google entrega refresh token para sincronizar después.
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
        }
        return f"{_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> OAuthTokens:
        datos = await self._token(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
            }
        )
        if CALENDAR_SCOPE not in str(datos.get("scope", "")).split():
            raise CalendarPermissionMissing()
        access_token = str(datos["access_token"])
        return OAuthTokens(
            access_token=access_token,
            refresh_token=_opcional(datos.get("refresh_token")),
            expires_at=self._vencimiento(datos),
            account_email=await self._email(access_token),
        )

    async def refresh(self, refresh_token: str) -> OAuthTokens:
        datos = await self._token({"grant_type": "refresh_token", "refresh_token": refresh_token})
        return OAuthTokens(
            access_token=str(datos["access_token"]),
            refresh_token=_opcional(datos.get("refresh_token")),
            expires_at=self._vencimiento(datos),
        )

    async def revoke(self, token: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as http:
                respuesta = await http.post(_REVOKE_URL, data={"token": token})
            if respuesta.status_code != 200:
                logger.info("Google no revocó el token (HTTP %s)", respuesta.status_code)
        except httpx.HTTPError as error:
            logger.warning("No se pudo revocar el token en Google: %s", type(error).__name__)

    async def create_event(self, access_token: str, draft: CalendarEventDraft) -> str:
        respuesta = await self._evento("POST", _EVENTS_URL, access_token, draft)
        evento_id = respuesta.json().get("id")
        if not evento_id:
            raise CalendarProviderUnavailable()
        return str(evento_id)

    async def update_event(self, access_token: str, event_id: str, draft: CalendarEventDraft) -> None:
        await self._evento("PATCH", f"{_EVENTS_URL}/{quote(event_id, safe='')}", access_token, draft)

    async def _evento(
        self, metodo: str, url: str, access_token: str, draft: CalendarEventDraft
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as http:
                respuesta = await http.request(
                    metodo,
                    url,
                    json=_cuerpo_evento(draft),
                    headers={"Authorization": f"Bearer {access_token}"},
                )
        except httpx.HTTPError as error:
            raise CalendarProviderUnavailable() from error
        if respuesta.status_code == 200:
            return respuesta
        if respuesta.status_code == 401:
            raise CalendarAuthExpired()
        if respuesta.status_code in (404, 410):
            raise CalendarEventNotFound()
        logger.error("Google Calendar rechazó el evento (HTTP %s)", respuesta.status_code)
        raise CalendarProviderUnavailable()

    async def _token(self, form: dict[str, str]) -> dict[str, object]:
        form = {**form, "client_id": self.client_id, "client_secret": self.client_secret}
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as http:
                respuesta = await http.post(_TOKEN_URL, data=form)
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
        logger.error("Google rechazó la petición de token (HTTP %s)", respuesta.status_code)
        raise CalendarProviderUnavailable()

    async def _email(self, access_token: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as http:
                respuesta = await http.get(
                    _USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
                )
        except httpx.HTTPError:
            return None
        if respuesta.status_code != 200:
            return None
        return _opcional(respuesta.json().get("email"))

    def _vencimiento(self, datos: dict[str, object]) -> datetime:
        segundos = datos.get("expires_in", 3600)
        return self.now() + timedelta(seconds=int(segundos) if isinstance(segundos, int | str) else 3600)


def _local(fecha: datetime) -> dict[str, str]:
    """UTC naive → hora de Chile con su zona: Google aplica el cambio de horario."""
    local = fecha.replace(tzinfo=UTC).astimezone(CHILE_TZ).replace(tzinfo=None)
    return {"dateTime": local.isoformat(timespec="seconds"), "timeZone": "America/Santiago"}


def _cuerpo_evento(draft: CalendarEventDraft) -> dict[str, object]:
    recordatorios: list[dict[str, object]] = [
        {"method": "popup", "minutes": minutos} for minutos in draft.reminders_minutes
    ]
    if draft.reminders_minutes:
        recordatorios.append({"method": "email", "minutes": max(draft.reminders_minutes)})
    return {
        "summary": draft.title,
        "description": draft.description,
        "start": _local(draft.start),
        "end": _local(draft.end),
        "reminders": {"useDefault": False, "overrides": recordatorios},
        "source": {"title": "ProyectosYA", "url": draft.return_url},
        "extendedProperties": {"private": {"milestone_id": str(draft.milestone_id)}},
    }


def _opcional(valor: object) -> str | None:
    return str(valor) if valor else None


def _error_oauth(respuesta: httpx.Response) -> str | None:
    try:
        datos = respuesta.json()
    except ValueError:
        return None
    return datos.get("error") if isinstance(datos, dict) else None
