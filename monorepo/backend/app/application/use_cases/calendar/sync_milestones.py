from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time
from uuid import UUID

from pydantic import SecretStr

from app.application.repositories.calendar_repository import (
    ICalendarConnectionRepository,
    ICalendarEventLinkRepository,
)
from app.application.repositories.tender_milestone_repository import (
    ITenderMilestoneRepository,
)
from app.application.repositories.tender_repository import ITenderRepository
from app.application.services.calendar_provider_client import (
    CalendarProviders,
    ICalendarProviderClient,
)
from app.application.use_cases.calendar.calendar_authorization import provider_client
from app.application.use_cases.milestones.milestone_views import get_tender
from app.domain.entities.calendar import (
    CalendarConnection,
    CalendarConnectionStatus,
    CalendarEventDraft,
    CalendarEventLink,
    CalendarProvider,
)
from app.domain.errors.calendar_errors import (
    CalendarAuthExpired,
    CalendarEventNotFound,
    CalendarNotConnected,
    CalendarProviderUnavailable,
    MilestoneTimeRequired,
)
from app.domain.errors.milestone_errors import MilestoneNotFound
from app.shared.datetime_utils import utc_now_naive


@dataclass(frozen=True)
class MilestoneSyncResult:
    milestone_id: UUID
    synced: bool


@dataclass(frozen=True)
class SyncResult:
    results: list[MilestoneSyncResult]

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if not r.synced)


class SyncMilestonesToCalendarUseCase:
    """Crea o actualiza en el calendario externo un evento por hito (criterios 3, 6 y 7).

    Un hito que falla no detiene a los demás: se informa por hito para que el
    reintento reenvíe solo los fallidos.
    """

    def __init__(
        self,
        tenders: ITenderRepository,
        milestones: ITenderMilestoneRepository,
        connections: ICalendarConnectionRepository,
        event_links: ICalendarEventLinkRepository,
        providers: CalendarProviders,
        app_base_url: str,
        now: Callable[[], datetime] = utc_now_naive,
    ):
        self.tenders = tenders
        self.milestones = milestones
        self.connections = connections
        self.event_links = event_links
        self.providers = providers
        self.app_base_url = app_base_url.rstrip("/")
        self.now = now

    async def execute(
        self,
        user_id: UUID,
        provider: CalendarProvider,
        tender_id: UUID,
        milestone_ids: list[UUID],
        default_time: time | None,
    ) -> SyncResult:
        client = provider_client(self.providers, provider)
        tender = await get_tender(self.tenders, tender_id)
        pedidos = set(milestone_ids)
        hitos = [
            h for h in await self.milestones.list_by_ids(user_id, list(pedidos))
            if h.tender_id == tender_id
        ]
        if not pedidos or {h.id for h in hitos} != pedidos:
            raise MilestoneNotFound()

        sin_hora = [h.id for h in hitos if not h.has_time]
        if sin_hora and default_time is None:
            raise MilestoneTimeRequired(sin_hora)

        conexion = await self._conexion_vigente(user_id, provider, client)
        enlaces = {
            e.milestone_id: e
            for e in await self.event_links.list_by_milestones(list(pedidos), provider)
        }
        return_url = f"{self.app_base_url}/matches/{tender_id}"

        resultados: list[MilestoneSyncResult] = []
        for hito in hitos:
            efectivo = hito if hito.has_time or default_time is None else hito.con_hora(default_time)
            borrador = CalendarEventDraft.from_milestone(
                efectivo, tender_title=tender.name, return_url=return_url
            )
            enlace = enlaces.get(hito.id)
            try:
                evento_id, conexion = await self._enviar(client, conexion, enlace, borrador)
            except CalendarProviderUnavailable:
                resultados.append(MilestoneSyncResult(milestone_id=hito.id, synced=False))
                continue
            await self.event_links.save(
                CalendarEventLink(
                    user_id=user_id,
                    milestone_id=hito.id,
                    provider=provider,
                    external_event_id=evento_id,
                    synced_due_at=efectivo.due_at,
                    last_synced_at=self.now(),
                )
            )
            resultados.append(MilestoneSyncResult(milestone_id=hito.id, synced=True))
        return SyncResult(results=resultados)

    async def _conexion_vigente(
        self, user_id: UUID, provider: CalendarProvider, client: ICalendarProviderClient
    ) -> CalendarConnection:
        conexion = await self.connections.get(user_id, provider)
        if conexion is None:
            raise CalendarNotConnected()
        if conexion.status is not CalendarConnectionStatus.ACTIVE:
            raise CalendarAuthExpired()
        if conexion.needs_refresh(self.now()):
            conexion = await self._refrescar(conexion, client)
        return conexion

    async def _refrescar(
        self, conexion: CalendarConnection, client: ICalendarProviderClient
    ) -> CalendarConnection:
        try:
            tokens = await client.refresh(conexion.refresh_token.get_secret_value())
        except CalendarAuthExpired:
            await self._marcar_revocada(conexion)
            raise
        nueva = conexion.model_copy(
            update={
                "access_token": SecretStr(tokens.access_token),
                "refresh_token": (
                    SecretStr(tokens.refresh_token) if tokens.refresh_token else conexion.refresh_token
                ),
                "expires_at": tokens.expires_at,
                "updated_at": self.now(),
            }
        )
        await self.connections.save(nueva)
        return nueva

    async def _marcar_revocada(self, conexion: CalendarConnection) -> None:
        await self.connections.save(
            conexion.model_copy(
                update={"status": CalendarConnectionStatus.REVOKED, "updated_at": self.now()}
            )
        )

    async def _enviar(
        self,
        client: ICalendarProviderClient,
        conexion: CalendarConnection,
        enlace: CalendarEventLink | None,
        borrador: CalendarEventDraft,
    ) -> tuple[str, CalendarConnection]:
        try:
            return await self._crear_o_actualizar(client, conexion, enlace, borrador), conexion
        except CalendarAuthExpired:
            # El token puede rechazarse antes de su vencimiento (p. ej. si el
            # usuario cambió su contraseña): se refresca una vez y se reintenta.
            conexion = await self._refrescar(conexion, client)
        try:
            return await self._crear_o_actualizar(client, conexion, enlace, borrador), conexion
        except CalendarAuthExpired:
            await self._marcar_revocada(conexion)
            raise

    @staticmethod
    async def _crear_o_actualizar(
        client: ICalendarProviderClient,
        conexion: CalendarConnection,
        enlace: CalendarEventLink | None,
        borrador: CalendarEventDraft,
    ) -> str:
        token = conexion.access_token.get_secret_value()
        if enlace is not None:
            try:
                await client.update_event(token, enlace.external_event_id, borrador)
                return enlace.external_event_id
            except CalendarEventNotFound:
                pass
        return await client.create_event(token, borrador)
