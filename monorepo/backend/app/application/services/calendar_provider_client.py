from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from app.domain.entities.calendar import CalendarEventDraft, CalendarProvider


@dataclass(frozen=True)
class OAuthTokens:
    access_token: str
    # Google solo lo entrega en el primer consentimiento y no al refrescar.
    refresh_token: str | None
    expires_at: datetime
    account_email: str | None = None


class ICalendarProviderClient(ABC):
    """Cliente de un calendario externo (Google hoy; Outlook después)."""

    @abstractmethod
    def authorization_url(self, state: str) -> str: ...

    @abstractmethod
    async def exchange_code(self, code: str) -> OAuthTokens:
        """Lanza CalendarAuthExpired, CalendarPermissionMissing o CalendarProviderUnavailable."""

    @abstractmethod
    async def refresh(self, refresh_token: str) -> OAuthTokens:
        """Lanza CalendarAuthExpired si el refresh token ya no sirve."""

    @abstractmethod
    async def revoke(self, token: str) -> None:
        """Mejor esfuerzo: no lanza si el proveedor rechaza la revocación."""

    @abstractmethod
    async def create_event(self, access_token: str, draft: CalendarEventDraft) -> str:
        """Devuelve el id del evento. Lanza CalendarAuthExpired si el token fue rechazado."""

    @abstractmethod
    async def update_event(self, access_token: str, event_id: str, draft: CalendarEventDraft) -> None:
        """Lanza CalendarEventNotFound si el usuario borró el evento."""


CalendarProviders = Mapping[CalendarProvider, ICalendarProviderClient]
