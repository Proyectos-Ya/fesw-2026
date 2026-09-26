from dataclasses import dataclass
from uuid import UUID

from app.application.repositories.calendar_repository import (
    ICalendarConnectionRepository,
)
from app.application.services.calendar_provider_client import CalendarProviders
from app.application.use_cases.calendar.calendar_authorization import provider_client
from app.domain.entities.calendar import CalendarConnectionStatus, CalendarProvider


@dataclass(frozen=True)
class CalendarConnectionView:
    provider: CalendarProvider
    connected: bool
    account_email: str | None
    needs_reconnect: bool


class GetCalendarConnectionsUseCase:
    """Estado de conexión por proveedor configurado. Nunca expone tokens."""

    def __init__(self, connections: ICalendarConnectionRepository, providers: CalendarProviders):
        self.connections = connections
        self.providers = providers

    async def execute(self, user_id: UUID) -> list[CalendarConnectionView]:
        vistas = []
        for provider in self.providers:
            conexion = await self.connections.get(user_id, provider)
            activa = conexion is not None and conexion.status is CalendarConnectionStatus.ACTIVE
            vistas.append(
                CalendarConnectionView(
                    provider=provider,
                    connected=activa,
                    account_email=conexion.account_email if conexion else None,
                    needs_reconnect=conexion is not None and not activa,
                )
            )
        return vistas


class DisconnectCalendarUseCase:
    def __init__(self, connections: ICalendarConnectionRepository, providers: CalendarProviders):
        self.connections = connections
        self.providers = providers

    async def execute(self, user_id: UUID, provider: CalendarProvider) -> None:
        client = provider_client(self.providers, provider)
        conexion = await self.connections.get(user_id, provider)
        if conexion is None:
            return
        # Revocar el refresh token invalida también los access tokens emitidos con él.
        await client.revoke(conexion.refresh_token.get_secret_value())
        await self.connections.delete(user_id, provider)
