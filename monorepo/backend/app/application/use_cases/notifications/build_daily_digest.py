from app.application.repositories.notification_repository import (
    INotificationDeliveryRepository,
    INotificationPreferenceRepository,
    INotificationRepository,
)
from app.domain.entities.notification import NotificationDelivery


class BuildDailyDigestUseCase:
    """Agrupa en un solo correo los avisos de quienes eligieron resumen diario.

    En modo `daily_digest` el escaneo crea los avisos in-app pero no encola
    correo. Este caso de uso, que corre una vez al día, junta todo lo acumulado
    y arma una única entrega.
    """

    def __init__(
        self,
        preference_repo: INotificationPreferenceRepository,
        notification_repo: INotificationRepository,
        delivery_repo: INotificationDeliveryRepository,
        max_por_resumen: int = 20,
    ) -> None:
        self.preference_repo = preference_repo
        self.notification_repo = notification_repo
        self.delivery_repo = delivery_repo
        self.max_por_resumen = max_por_resumen

    async def execute(self) -> int:
        """Arma los resúmenes del día. Retorna cuántas entregas encoló."""
        preferencias = await self.preference_repo.list_by_delivery_mode("daily_digest")
        encoladas = 0

        for preference in preferencias:
            if not preference.wants_email():
                continue

            avisos = await self.notification_repo.list_by_user(
                preference.user_id, limit=self.max_por_resumen
            )
            if not avisos:
                continue

            # Un aviso que ya viajó (o va a viajar) en otro correo no se repite:
            # si alguien alterna entre inmediato y resumen, no debería recibir
            # dos veces la misma licitación.
            ya_entregados = await self.delivery_repo.list_pending_notification_ids(
                preference.user_id
            )
            pendientes = [a.id for a in avisos if a.id not in ya_entregados]
            if not pendientes:
                continue

            await self.delivery_repo.save(
                NotificationDelivery(
                    user_id=preference.user_id,
                    kind="digest",
                    notification_ids=pendientes,
                )
            )
            encoladas += 1

        return encoladas
