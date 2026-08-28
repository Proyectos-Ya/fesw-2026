"""Implementaciones SQLModel de los repositorios de alertas."""

from datetime import datetime
from uuid import UUID

from sqlmodel import col, desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.notification_repository import (
    INotificationDeliveryRepository,
    INotificationPreferenceRepository,
    INotificationRepository,
)
from app.domain.entities.notification import (
    DeliveryKind,
    DeliveryMode,
    DeliveryStatus,
    Notification,
    NotificationDelivery,
    NotificationPreference,
)
from app.infrastructure.repositories.notification_model import (
    NotificationDeliveryModel,
    NotificationModel,
    NotificationPreferenceModel,
)
from app.shared.datetime_utils import utc_now_naive


class NotificationPreferenceRepository(INotificationPreferenceRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: NotificationPreferenceModel) -> NotificationPreference:
        # La columna guarda un str libre, pero el dominio solo acepta los dos
        # valores válidos. Normalizar acá deja el borde de la base como único
        # lugar donde una fila inesperada se convierte en algo tipado.
        modo: DeliveryMode = (
            "daily_digest" if model.delivery_mode == "daily_digest" else "immediate"
        )
        return NotificationPreference(
            id=model.id,
            user_id=model.user_id,
            enabled=model.enabled,
            threshold=model.threshold,
            delivery_mode=modo,
            email_delivery_enabled=model.email_delivery_enabled,
            last_failure_reason=model.last_failure_reason,
            last_failure_at=model.last_failure_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def _get_model(self, user_id: UUID) -> NotificationPreferenceModel | None:
        result = await self.session.exec(
            select(NotificationPreferenceModel).where(
                NotificationPreferenceModel.user_id == user_id
            )
        )
        return result.first()

    async def get_by_user_id(self, user_id: UUID) -> NotificationPreference | None:
        model = await self._get_model(user_id)
        return self._to_entity(model) if model else None

    async def list_by_delivery_mode(
        self, delivery_mode: str
    ) -> list[NotificationPreference]:
        result = await self.session.exec(
            select(NotificationPreferenceModel).where(
                NotificationPreferenceModel.delivery_mode == delivery_mode,
                NotificationPreferenceModel.enabled == True,  # noqa: E712
            )
        )
        return [self._to_entity(m) for m in result.all()]

    async def save(self, preference: NotificationPreference) -> NotificationPreference:
        """Crea o actualiza. La unicidad de `user_id` hace de clave natural."""
        preference.updated_at = utc_now_naive()
        model = await self._get_model(preference.user_id)

        if model is None:
            model = NotificationPreferenceModel(
                id=preference.id,
                user_id=preference.user_id,
                created_at=preference.created_at,
                updated_at=preference.updated_at,
            )

        model.enabled = preference.enabled
        model.threshold = preference.threshold
        model.delivery_mode = preference.delivery_mode
        model.email_delivery_enabled = preference.email_delivery_enabled
        model.last_failure_reason = preference.last_failure_reason
        model.last_failure_at = preference.last_failure_at
        model.updated_at = preference.updated_at

        self.session.add(model)
        await self.session.commit()
        return self._to_entity(model)


class NotificationRepository(INotificationRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: NotificationModel) -> Notification:
        return Notification(
            id=model.id,
            user_id=model.user_id,
            tender_id=model.tender_id,
            score=model.score,
            read_at=model.read_at,
            created_at=model.created_at,
        )

    def _to_model(self, entity: Notification) -> NotificationModel:
        return NotificationModel(
            id=entity.id,
            user_id=entity.user_id,
            tender_id=entity.tender_id,
            score=entity.score,
            read_at=entity.read_at,
            created_at=entity.created_at,
        )

    async def get(self, notification_id: UUID) -> Notification | None:
        model = await self.session.get(NotificationModel, notification_id)
        return self._to_entity(model) if model else None

    async def list_by_user(
        self, user_id: UUID, only_unread: bool = False, limit: int = 50
    ) -> list[Notification]:
        consulta = select(NotificationModel).where(NotificationModel.user_id == user_id)
        if only_unread:
            consulta = consulta.where(col(NotificationModel.read_at).is_(None))
        consulta = consulta.order_by(desc(col(NotificationModel.created_at))).limit(
            limit
        )
        result = await self.session.exec(consulta)
        return [self._to_entity(m) for m in result.all()]

    async def list_by_ids(self, notification_ids: list[UUID]) -> list[Notification]:
        if not notification_ids:
            return []
        result = await self.session.exec(
            select(NotificationModel).where(
                col(NotificationModel.id).in_(notification_ids)
            )
        )
        return [self._to_entity(m) for m in result.all()]

    async def count_unread(self, user_id: UUID) -> int:
        result = await self.session.exec(
            select(NotificationModel).where(
                NotificationModel.user_id == user_id,
                col(NotificationModel.read_at).is_(None),
            )
        )
        return len(result.all())

    async def get_notified_tender_ids(self, user_id: UUID) -> set[UUID]:
        result = await self.session.exec(
            select(NotificationModel.tender_id).where(
                NotificationModel.user_id == user_id
            )
        )
        return set(result.all())

    async def save(self, notification: Notification) -> Notification:
        model = await self.session.get(NotificationModel, notification.id)
        if model is None:
            model = self._to_model(notification)
        else:
            model.read_at = notification.read_at
        self.session.add(model)
        await self.session.commit()
        return self._to_entity(model)

    async def save_bulk(self, notifications: list[Notification]) -> list[Notification]:
        if not notifications:
            return []
        for entity in notifications:
            self.session.add(self._to_model(entity))
        await self.session.commit()
        return notifications

    async def mark_all_read(self, user_id: UUID) -> int:
        result = await self.session.exec(
            select(NotificationModel).where(
                NotificationModel.user_id == user_id,
                col(NotificationModel.read_at).is_(None),
            )
        )
        modelos = list(result.all())
        ahora = utc_now_naive()
        for model in modelos:
            model.read_at = ahora
            self.session.add(model)
        await self.session.commit()
        return len(modelos)


class NotificationDeliveryRepository(INotificationDeliveryRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: NotificationDeliveryModel) -> NotificationDelivery:
        estado: DeliveryStatus = "pending"
        if model.status == "sent":
            estado = "sent"
        elif model.status == "failed_permanent":
            estado = "failed_permanent"
        tipo: DeliveryKind = "digest" if model.kind == "digest" else "immediate"
        return NotificationDelivery(
            id=model.id,
            user_id=model.user_id,
            kind=tipo,
            notification_ids=[UUID(v) for v in (model.notification_ids or [])],
            status=estado,
            attempts=model.attempts,
            last_error=model.last_error,
            next_attempt_at=model.next_attempt_at,
            sent_at=model.sent_at,
            created_at=model.created_at,
        )

    async def save(self, delivery: NotificationDelivery) -> NotificationDelivery:
        model = await self.session.get(NotificationDeliveryModel, delivery.id)
        if model is None:
            model = NotificationDeliveryModel(
                id=delivery.id,
                user_id=delivery.user_id,
                kind=delivery.kind,
                next_attempt_at=delivery.next_attempt_at,
                created_at=delivery.created_at,
            )
        # `notification_ids` se guarda como lista de str: la columna es JSON y
        # UUID no es serializable de forma nativa.
        model.notification_ids = [str(v) for v in delivery.notification_ids]
        model.status = delivery.status
        model.attempts = delivery.attempts
        model.last_error = delivery.last_error
        model.next_attempt_at = delivery.next_attempt_at
        model.sent_at = delivery.sent_at
        self.session.add(model)
        await self.session.commit()
        return self._to_entity(model)

    async def list_due(
        self, now: datetime, limit: int = 20
    ) -> list[NotificationDelivery]:
        result = await self.session.exec(
            select(NotificationDeliveryModel)
            .where(
                NotificationDeliveryModel.status == "pending",
                col(NotificationDeliveryModel.next_attempt_at) <= now,
            )
            .order_by(col(NotificationDeliveryModel.next_attempt_at))
            .limit(limit)
        )
        return [self._to_entity(m) for m in result.all()]

    async def list_by_user(
        self, user_id: UUID, limit: int = 50
    ) -> list[NotificationDelivery]:
        result = await self.session.exec(
            select(NotificationDeliveryModel)
            .where(NotificationDeliveryModel.user_id == user_id)
            .order_by(desc(col(NotificationDeliveryModel.created_at)))
            .limit(limit)
        )
        return [self._to_entity(m) for m in result.all()]

    async def list_pending_notification_ids(self, user_id: UUID) -> set[UUID]:
        result = await self.session.exec(
            select(NotificationDeliveryModel).where(
                NotificationDeliveryModel.user_id == user_id
            )
        )
        ids: set[UUID] = set()
        for model in result.all():
            for valor in model.notification_ids or []:
                ids.add(UUID(valor))
        return ids
