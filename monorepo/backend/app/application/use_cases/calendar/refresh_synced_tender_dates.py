import logging
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from app.application.repositories.calendar_repository import (
    ICalendarEventLinkRepository,
)
from app.application.repositories.notification_repository import (
    INotificationDeliveryRepository,
    INotificationPreferenceRepository,
    INotificationRepository,
)
from app.application.repositories.tender_milestone_repository import (
    ITenderMilestoneRepository,
)
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.services.tender_refresher import (
    ITenderRefresher,
    OfficialTenderDates,
)
from app.application.use_cases.calendar.sync_milestones import (
    SyncMilestonesToCalendarUseCase,
)
from app.domain.entities.calendar import CalendarEventLink
from app.domain.entities.notification import (
    MilestoneDateChange,
    Notification,
    NotificationDelivery,
    NotificationPreference,
)
from app.domain.entities.tender import Tender
from app.domain.entities.tender_milestone import MilestoneKind, MilestoneSource
from app.domain.errors.calendar_errors import CalendarError
from app.domain.errors.milestone_errors import MilestoneNotFound
from app.shared.datetime_utils import utc_now_naive

logger = logging.getLogger(__name__)

# Etiquetas iguales a los títulos de los hitos oficiales (mercado_publico_milestones).
_OFICIALES: tuple[tuple[MilestoneKind, str, str], ...] = (
    (MilestoneKind.PUBLICACION, "published_at", "Publicación en Mercado Público"),
    (MilestoneKind.CIERRE_POSTULACION, "closing_at", "Cierre de recepción de ofertas"),
)


class RefreshSyncedTenderDatesUseCase:
    """Detecta cambios de fechas oficiales en licitaciones con hitos sincronizados (criterio 4).

    Solo revisa licitaciones que alguien tiene en su calendario y que siguen
    abiertas: son las únicas donde un cambio mueve un evento, y así la cuota de
    Mercado Público no se gasta en el resto del corpus.
    """

    def __init__(
        self,
        tenders: ITenderRepository,
        refresher: ITenderRefresher,
        milestones: ITenderMilestoneRepository,
        event_links: ICalendarEventLinkRepository,
        sync: SyncMilestonesToCalendarUseCase,
        notifications: INotificationRepository,
        deliveries: INotificationDeliveryRepository,
        preferences: INotificationPreferenceRepository,
        now: Callable[[], datetime] = utc_now_naive,
    ):
        self.tenders = tenders
        self.refresher = refresher
        self.milestones = milestones
        self.event_links = event_links
        self.sync = sync
        self.notifications = notifications
        self.deliveries = deliveries
        self.preferences = preferences
        self.now = now

    async def execute(self) -> int:
        """Devuelve cuántas licitaciones cambiaron de fecha."""
        tender_ids = await self.event_links.list_linked_tender_ids()
        if not tender_ids:
            return 0
        ahora = self.now()
        cambiadas = 0
        for tender in await self.tenders.get_tenders(TenderFilters(ids=tender_ids)):
            if tender.closing_at < ahora:
                continue
            try:
                oficiales = await self.refresher.refresh(tender.code)
            except Exception as error:
                logger.warning(
                    "No se pudieron refrescar las fechas de %s: %s", tender.code, error
                )
                continue
            if oficiales is None:
                continue
            cambios = _cambios(tender, oficiales)
            if cambios:
                await self._aplicar(tender, cambios)
                cambiadas += 1
        return cambiadas

    async def _aplicar(
        self, tender: Tender, cambios: dict[MilestoneKind, MilestoneDateChange]
    ) -> None:
        ahora = self.now()
        oficiales = await self.milestones.list_by_tender_and_source(
            tender.id, MilestoneSource.MERCADO_PUBLICO
        )
        movidos = [
            m.model_copy(update={"due_at": cambios[m.kind].new_at, "updated_at": ahora})
            for m in oficiales
            if m.kind in cambios
        ]
        await self.milestones.save_many(movidos)

        enlaces = await self.event_links.list_by_tender(tender.id)
        ids_movidos = {m.id for m in movidos}
        for user_id in {e.user_id for e in enlaces}:
            await self._actualizar_calendario(
                user_id, tender.id, [e for e in enlaces if e.user_id == user_id and e.milestone_id in ids_movidos]
            )
            await self._avisar(user_id, tender.id, list(cambios.values()))

    async def _actualizar_calendario(
        self, user_id: UUID, tender_id: UUID, enlaces: list[CalendarEventLink]
    ) -> None:
        for provider in {e.provider for e in enlaces}:
            ids = [e.milestone_id for e in enlaces if e.provider is provider]
            try:
                resultado = await self.sync.execute(user_id, provider, tender_id, ids, None)
            except (CalendarError, MilestoneNotFound) as error:
                # El aviso sale igual: el usuario se entera y puede reconectar.
                logger.warning("No se actualizó el calendario de %s: %s", user_id, error)
                continue
            if resultado.failed_count:
                logger.warning(
                    "%s eventos de %s no se actualizaron", resultado.failed_count, user_id
                )

    async def _avisar(
        self, user_id: UUID, tender_id: UUID, cambios: list[MilestoneDateChange]
    ) -> None:
        aviso = await self.notifications.save_date_change(
            Notification(
                user_id=user_id,
                tender_id=tender_id,
                kind="date_changed",
                date_changes=cambios,
                created_at=self.now(),
            )
        )
        preferencia = await self.preferences.get_by_user_id(user_id) or NotificationPreference(
            user_id=user_id
        )
        # Sale al momento aunque el usuario use resumen diario: un plazo movido
        # no puede esperar al día siguiente.
        if preferencia.wants_email():
            await self.deliveries.save(
                NotificationDelivery(
                    user_id=user_id,
                    kind="immediate",
                    notification_ids=[aviso.id],
                    next_attempt_at=self.now(),
                )
            )


def _cambios(
    tender: Tender, oficiales: OfficialTenderDates
) -> dict[MilestoneKind, MilestoneDateChange]:
    cambios: dict[MilestoneKind, MilestoneDateChange] = {}
    for kind, campo, etiqueta in _OFICIALES:
        antes: datetime = getattr(tender, campo)
        ahora: datetime = getattr(oficiales, campo)
        if antes != ahora:
            cambios[kind] = MilestoneDateChange(label=etiqueta, previous_at=antes, new_at=ahora)
    return cambios
