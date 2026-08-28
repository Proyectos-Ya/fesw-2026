from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.entities.notification import (
    Notification,
    NotificationDelivery,
    NotificationPreference,
)


class INotificationPreferenceRepository(ABC):
    """Persistencia de las preferencias de alertas."""

    @abstractmethod
    async def get_by_user_id(self, user_id: UUID) -> NotificationPreference | None:
        """Preferencias del usuario, o None si nunca las guardó."""
        pass

    @abstractmethod
    async def list_by_delivery_mode(
        self, delivery_mode: str
    ) -> list[NotificationPreference]:
        """Preferencias activas con ese modo de entrega.

        Lo usa el resumen diario, que solo debe recorrer a quien lo pidió.
        """
        pass

    @abstractmethod
    async def save(self, preference: NotificationPreference) -> NotificationPreference:
        """Crea o actualiza las preferencias del usuario."""
        pass


class INotificationRepository(ABC):
    """Persistencia de los avisos in-app."""

    @abstractmethod
    async def get(self, notification_id: UUID) -> Notification | None:
        pass

    @abstractmethod
    async def list_by_user(
        self, user_id: UUID, only_unread: bool = False, limit: int = 50
    ) -> list[Notification]:
        """Avisos del usuario, del más reciente al más antiguo."""
        pass

    @abstractmethod
    async def list_by_ids(self, notification_ids: list[UUID]) -> list[Notification]:
        """Avisos por id, para armar el cuerpo de un correo."""
        pass

    @abstractmethod
    async def count_unread(self, user_id: UUID) -> int:
        pass

    @abstractmethod
    async def get_notified_tender_ids(self, user_id: UUID) -> set[UUID]:
        """Licitaciones de las que ya se avisó a este usuario.

        Es lo que impide que cada escaneo repita los mismos avisos.
        """
        pass

    @abstractmethod
    async def save_bulk(self, notifications: list[Notification]) -> list[Notification]:
        pass

    @abstractmethod
    async def save(self, notification: Notification) -> Notification:
        pass

    @abstractmethod
    async def mark_all_read(self, user_id: UUID) -> int:
        """Marca todos los avisos del usuario como leídos. Retorna cuántos cambió."""
        pass


class INotificationDeliveryRepository(ABC):
    """Persistencia de la cola de salida de correos."""

    @abstractmethod
    async def save(self, delivery: NotificationDelivery) -> NotificationDelivery:
        pass

    @abstractmethod
    async def list_due(
        self, now: datetime, limit: int = 20
    ) -> list[NotificationDelivery]:
        """Entregas pendientes cuyo próximo intento ya venció."""
        pass

    @abstractmethod
    async def list_by_user(
        self, user_id: UUID, limit: int = 50
    ) -> list[NotificationDelivery]:
        """Bandeja de salida del usuario, de la más reciente a la más antigua."""
        pass

    @abstractmethod
    async def list_pending_notification_ids(self, user_id: UUID) -> set[UUID]:
        """Avisos del usuario que ya tienen una entrega asociada.

        El resumen diario los usa para no volver a incluir lo que ya salió (o
        está por salir) en un correo inmediato.
        """
        pass
