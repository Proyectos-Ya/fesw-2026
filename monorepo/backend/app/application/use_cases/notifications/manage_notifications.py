"""Casos de uso de lectura y gestión de los avisos in-app.

Van juntos porque son operaciones cortas sobre la misma entidad; la lógica de
detección y de envío, que sí es densa, vive en sus propios módulos.
"""

from dataclasses import dataclass
from uuid import UUID

from app.application.repositories.notification_repository import (
    INotificationDeliveryRepository,
    INotificationPreferenceRepository,
    INotificationRepository,
)
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.domain.entities.notification import (
    Notification,
    NotificationDelivery,
    NotificationPreference,
)
from app.domain.entities.tender import Tender
from app.domain.errors.notification_errors import NotificationNotFound
from app.shared.constants import ACTIVE_TENDER_STATUSES
from app.shared.datetime_utils import utc_now_naive


@dataclass
class NotificationWithTender:
    """Un aviso junto con la licitación que lo motivó.

    `is_closed` se calcula acá y no en el frontend para que el aviso pueda
    advertir que la licitación ya cerró sin que la interfaz repita la regla.
    """

    notification: Notification
    tender: Tender | None
    is_closed: bool


class ListNotificationsUseCase:
    def __init__(
        self,
        notification_repo: INotificationRepository,
        tender_repo: ITenderRepository,
    ) -> None:
        self.notification_repo = notification_repo
        self.tender_repo = tender_repo

    async def execute(
        self, user_id: UUID, only_unread: bool = False, limit: int = 50
    ) -> list[NotificationWithTender]:
        avisos = await self.notification_repo.list_by_user(
            user_id, only_unread=only_unread, limit=limit
        )
        if not avisos:
            return []

        tenders = await self.tender_repo.get_tenders(
            TenderFilters(ids=[a.tender_id for a in avisos])
        )
        tender_por_id = {t.id: t for t in tenders}
        ahora = utc_now_naive()

        resultado: list[NotificationWithTender] = []
        for aviso in avisos:
            tender = tender_por_id.get(aviso.tender_id)
            cerrada = tender is None or (
                tender.closing_at <= ahora
                or tender.status_code not in ACTIVE_TENDER_STATUSES
            )
            resultado.append(
                NotificationWithTender(
                    notification=aviso, tender=tender, is_closed=cerrada
                )
            )
        return resultado


class CountUnreadNotificationsUseCase:
    def __init__(self, notification_repo: INotificationRepository) -> None:
        self.notification_repo = notification_repo

    async def execute(self, user_id: UUID) -> int:
        return await self.notification_repo.count_unread(user_id)


class MarkNotificationReadUseCase:
    def __init__(self, notification_repo: INotificationRepository) -> None:
        self.notification_repo = notification_repo

    async def execute(self, user_id: UUID, notification_id: UUID) -> Notification:
        aviso = await self.notification_repo.get(notification_id)
        # Comprobar el dueño evita que un id ajeno se marque como leído; para
        # quien no lo posee, el aviso simplemente no existe.
        if aviso is None or aviso.user_id != user_id:
            raise NotificationNotFound(str(notification_id))

        aviso.mark_read()
        return await self.notification_repo.save(aviso)


class MarkAllNotificationsReadUseCase:
    def __init__(self, notification_repo: INotificationRepository) -> None:
        self.notification_repo = notification_repo

    async def execute(self, user_id: UUID) -> int:
        return await self.notification_repo.mark_all_read(user_id)


class GetNotificationPreferencesUseCase:
    def __init__(self, preference_repo: INotificationPreferenceRepository) -> None:
        self.preference_repo = preference_repo

    async def execute(self, user_id: UUID) -> NotificationPreference:
        """Devuelve las preferencias, o los defaults si nunca las guardó.

        No persiste: leer las preferencias no debería escribir en la base.
        """
        preferencia = await self.preference_repo.get_by_user_id(user_id)
        return preferencia or NotificationPreference(user_id=user_id)


class UpdateNotificationPreferencesUseCase:
    def __init__(self, preference_repo: INotificationPreferenceRepository) -> None:
        self.preference_repo = preference_repo

    async def execute(
        self,
        user_id: UUID,
        enabled: bool | None = None,
        threshold: float | None = None,
        delivery_mode: str | None = None,
        reactivate_email: bool = False,
    ) -> NotificationPreference:
        actual = await self.preference_repo.get_by_user_id(user_id)
        if actual is None:
            actual = NotificationPreference(user_id=user_id)

        if enabled is not None:
            actual.enabled = enabled
        if threshold is not None:
            # Reasignar dispara el validador del dominio: un umbral fuera de
            # (0, 1] revienta acá y no cuando el escaneo no avise nunca.
            actual.threshold = NotificationPreference(
                user_id=user_id, threshold=threshold
            ).threshold
        if delivery_mode is not None:
            if delivery_mode not in ("immediate", "daily_digest"):
                raise ValueError("El modo de entrega no es válido")
            actual.delivery_mode = (
                "daily_digest" if delivery_mode == "daily_digest" else "immediate"
            )
        if reactivate_email:
            actual.email_delivery_enabled = True
            actual.last_failure_reason = None
            actual.last_failure_at = None

        return await self.preference_repo.save(actual)


class ListDeliveriesUseCase:
    """Bandeja de salida del usuario: qué correos salieron y cuáles esperan."""

    def __init__(self, delivery_repo: INotificationDeliveryRepository) -> None:
        self.delivery_repo = delivery_repo

    async def execute(
        self, user_id: UUID, limit: int = 50
    ) -> list[NotificationDelivery]:
        return await self.delivery_repo.list_by_user(user_id, limit=limit)
