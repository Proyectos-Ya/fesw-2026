"""Notificaciones a miembros del workspace tras una mutación kanban (HU-18).

Se invoca desde el router vía `BackgroundTasks` después de que el use case de
mutación respondió. Si falla el aviso, la mutación ya está persistida: la
notificación es informativa, no transaccional.

Reglas:
- No avisa al actor (`actor_user_id`): mover una tarjeta no debería generar
  tu propio aviso.
- Solo avisa a miembros activos que explícitamente activaron
  `kanban_notifications_enabled` en sus preferencias. Default es False.
"""

from uuid import UUID

from app.application.repositories.notification_repository import (
    INotificationPreferenceRepository,
    INotificationRepository,
)
from app.application.repositories.supplier_member_repository import (
    ISupplierMemberRepository,
)
from app.domain.entities.notification import Notification
from app.domain.entities.supplier_member import MemberStatus


class NotifyKanbanChangeUseCase:
    def __init__(
        self,
        member_repo: ISupplierMemberRepository,
        preference_repo: INotificationPreferenceRepository,
        notification_repo: INotificationRepository,
    ):
        self.member_repo = member_repo
        self.preference_repo = preference_repo
        self.notification_repo = notification_repo

    async def execute(
        self,
        *,
        supplier_id: UUID,
        actor_user_id: UUID,
        tender_id: UUID | None = None,
    ) -> list[Notification]:
        members = await self.member_repo.list_by_supplier_id(
            supplier_id, status=MemberStatus.ACTIVE
        )

        recipients: list[UUID] = []
        for member in members:
            if member.user_id == actor_user_id:
                continue
            preference = await self.preference_repo.get_by_user_id(member.user_id)
            if preference is None or not preference.kanban_notifications_enabled:
                continue
            recipients.append(member.user_id)

        if not recipients:
            return []

        # El tender_id es NOT NULL en el schema actual de notification; para
        # eventos de columna (sin tender) usamos el supplier_id como placeholder.
        # Si la DB termina siendo nullable, cambiar a None explícito.
        # Un aviso por usuario y licitación: el siguiente cambio lo reemplaza y
        # lo vuelve a marcar sin leer, en vez de chocar con el unique de la tabla.
        return [
            await self.notification_repo.save_kanban_change(
                Notification(
                    user_id=uid,
                    tender_id=tender_id or supplier_id,
                    kind="kanban_change",
                    score=None,
                )
            )
            for uid in recipients
        ]
