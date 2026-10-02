import logging
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

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
from app.domain.entities.notification import (
    MilestoneReminder,
    Notification,
    NotificationDelivery,
    NotificationPreference,
)
from app.domain.entities.tender_milestone import TenderMilestone
from app.shared.datetime_utils import utc_now_naive

logger = logging.getLogger(__name__)


class SendMilestoneRemindersUseCase:
    """Avisa de los hitos con recordatorio activado que están por vencer (criterio 10).

    Corre en un bucle propio. El control de "ya avisé" vive en el hito
    (`reminder_sent_at`) y no en la tabla de avisos, porque el aviso se agrupa
    por licitación y puede cubrir varios hitos a la vez.
    """

    def __init__(
        self,
        tenders: ITenderRepository,
        milestones: ITenderMilestoneRepository,
        notifications: INotificationRepository,
        deliveries: INotificationDeliveryRepository,
        preferences: INotificationPreferenceRepository,
        now: Callable[[], datetime] = utc_now_naive,
    ):
        self.tenders = tenders
        self.milestones = milestones
        self.notifications = notifications
        self.deliveries = deliveries
        self.preferences = preferences
        self.now = now

    async def execute(self) -> int:
        """Devuelve cuántos hitos se recordaron."""
        ahora = self.now()
        pendientes = await self.milestones.list_pending_reminders(ahora)
        if not pendientes:
            return 0

        # Corte obligatorio: `get_tenders` sin ids traería la base entera.
        tender_ids = list({h.tender_id for h in pendientes})
        conocidas = {t.id for t in await self.tenders.get_tenders(TenderFilters(ids=tender_ids))}

        recordados = 0
        for (user_id, tender_id), hitos in _agrupar(pendientes).items():
            if tender_id not in conocidas:
                # La licitación desapareció: no hay ficha que enlazar.
                logger.info("Se omite el recordatorio de una licitación que ya no existe")
                continue
            await self._avisar(user_id, tender_id, hitos, ahora)
            await self.milestones.save_many(
                [h.con_recordatorio_enviado(ahora) for h in hitos]
            )
            recordados += len(hitos)
        return recordados

    async def _avisar(
        self,
        user_id: UUID,
        tender_id: UUID,
        hitos: list[TenderMilestone],
        ahora: datetime,
    ) -> None:
        aviso = await self.notifications.save_milestone_reminder(
            Notification(
                user_id=user_id,
                tender_id=tender_id,
                kind="milestone_reminder",
                milestone_reminders=[
                    MilestoneReminder(milestone_id=h.id, title=h.title, due_at=h.due_at)
                    for h in hitos
                ],
                created_at=ahora,
            )
        )
        preferencia = await self.preferences.get_by_user_id(user_id) or NotificationPreference(
            user_id=user_id
        )
        # El recordatorio sale al momento: agruparlo en el resumen diario podría
        # entregarlo después del propio vencimiento.
        if preferencia.wants_email():
            await self.deliveries.save(
                NotificationDelivery(
                    user_id=user_id,
                    kind="immediate",
                    notification_ids=[aviso.id],
                    next_attempt_at=ahora,
                )
            )


def _agrupar(
    hitos: list[TenderMilestone],
) -> dict[tuple[UUID, UUID], list[TenderMilestone]]:
    """Un aviso por usuario y licitación, aunque venzan varios hitos a la vez."""
    grupos: dict[tuple[UUID, UUID], list[TenderMilestone]] = {}
    for hito in hitos:
        grupos.setdefault((hito.user_id, hito.tender_id), []).append(hito)
    return grupos
