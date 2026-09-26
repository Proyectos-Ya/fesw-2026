from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from app.domain.entities.calendar import CalendarProvider


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


CalendarProviders = Mapping[CalendarProvider, ICalendarProviderClient]
