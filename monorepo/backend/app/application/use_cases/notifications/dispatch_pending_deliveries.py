from datetime import datetime

from app.application.repositories.notification_repository import (
    INotificationDeliveryRepository,
    INotificationPreferenceRepository,
    INotificationRepository,
)
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.repositories.user_repository import IUserRepository
from app.application.services.email_service import EmailMessage, IEmailService
from app.application.services.email_templates import (
    AlertItem,
    DateChangeItem,
    build_date_change_html_body,
    build_date_change_subject,
    build_date_change_text_body,
    build_html_body,
    build_subject,
    build_text_body,
)
from app.domain.entities.notification import (
    NotificationDelivery,
    NotificationPreference,
)
from app.domain.errors.notification_errors import (
    PermanentEmailError,
    TransientEmailError,
)
from app.shared.datetime_utils import utc_now_naive


class DispatchPendingDeliveriesUseCase:
    """Vacía la cola de correos de alerta.

    Corre en bucle cada pocos segundos. Es lo que hace que, cuando el servicio
    de mensajería vuelve, lo que quedó "Pendiente" salga solo, sin que nadie
    tenga que reintentar a mano.
    """

    def __init__(
        self,
        delivery_repo: INotificationDeliveryRepository,
        notification_repo: INotificationRepository,
        preference_repo: INotificationPreferenceRepository,
        user_repo: IUserRepository,
        tender_repo: ITenderRepository,
        email_service: IEmailService,
        base_url: str,
    ) -> None:
        self.delivery_repo = delivery_repo
        self.notification_repo = notification_repo
        self.preference_repo = preference_repo
        self.user_repo = user_repo
        self.tender_repo = tender_repo
        self.email_service = email_service
        self.base_url = base_url

    async def _build_message(
        self, delivery: NotificationDelivery, to: str
    ) -> EmailMessage | None:
        """El correo de la entrega, o None si ya no queda nada que informar."""
        notificaciones = await self.notification_repo.list_by_ids(
            delivery.notification_ids
        )
        if not notificaciones:
            return None

        # Corte obligatorio: `get_tenders` sin ids traería la base entera.
        tender_ids = [n.tender_id for n in notificaciones]
        tenders = await self.tender_repo.get_tenders(TenderFilters(ids=tender_ids))
        tender_por_id = {t.id: t for t in tenders}

        # Una entrega de "Fecha modificada" (HU-16) solo lleva avisos de ese tipo.
        cambios = [
            DateChangeItem(
                tender_id=tender.id,
                title=tender.name,
                changes=[(c.label, c.previous_at, c.new_at) for c in n.date_changes],
            )
            for n in notificaciones
            if n.kind == "date_changed" and (tender := tender_por_id.get(n.tender_id))
        ]
        if cambios:
            return EmailMessage(
                to=to,
                subject=build_date_change_subject(cambios),
                text_body=build_date_change_text_body(cambios, self.base_url),
                html_body=build_date_change_html_body(cambios, self.base_url),
            )

        items = [
            AlertItem(
                tender_id=tender.id,
                title=tender.name,
                buyer_name=tender.buyer_name,
                closing_at=tender.closing_at,
                score=n.score,
            )
            for n in notificaciones
            if n.kind == "match"
            and n.score is not None
            and (tender := tender_por_id.get(n.tender_id))
        ]
        if not items:
            return None
        es_resumen = delivery.kind == "digest"
        return EmailMessage(
            to=to,
            subject=build_subject(items, es_resumen),
            text_body=build_text_body(items, self.base_url, es_resumen),
            html_body=build_html_body(items, self.base_url, es_resumen),
        )

    async def _desactivar_correo(
        self, preference: NotificationPreference, motivo: str, ahora: datetime
    ) -> None:
        preference.email_delivery_enabled = False
        preference.last_failure_reason = motivo
        preference.last_failure_at = ahora
        await self.preference_repo.save(preference)

    async def execute(self, now: datetime | None = None, limit: int = 20) -> int:
        """Procesa las entregas vencidas. Retorna cuántos correos salieron."""
        ahora = now or utc_now_naive()
        pendientes = await self.delivery_repo.list_due(ahora, limit)
        enviados = 0

        for delivery in pendientes:
            preference = await self.preference_repo.get_by_user_id(delivery.user_id)
            if preference is None:
                preference = NotificationPreference(user_id=delivery.user_id)

            if not preference.wants_email():
                # El usuario apagó el correo entre que se encoló y ahora. Se
                # cierra la entrega en vez de dejarla girando para siempre.
                delivery.mark_failed_permanent(
                    "Envío de correo desactivado para este usuario", ahora
                )
                await self.delivery_repo.save(delivery)
                continue

            user = await self.user_repo.get_by_id(delivery.user_id)
            if user is None:
                delivery.mark_failed_permanent("El usuario ya no existe", ahora)
                await self.delivery_repo.save(delivery)
                continue

            mensaje = await self._build_message(delivery, user.email)
            if mensaje is None:
                # Las licitaciones desaparecieron de la base: no hay correo que
                # mandar y reintentar no las va a traer de vuelta.
                delivery.mark_failed_permanent(
                    "No quedan licitaciones que informar en este aviso", ahora
                )
                await self.delivery_repo.save(delivery)
                continue

            try:
                await self.email_service.send(mensaje)
            except TransientEmailError as exc:
                # Servicio caído: queda "Pendiente" y se reintenta más tarde.
                delivery.register_transient_failure(exc.message, ahora)
            except PermanentEmailError as exc:
                # La dirección no existe: se registra el fallo y se corta el
                # envío para ese usuario, que lo verá en sus notificaciones.
                delivery.mark_failed_permanent(exc.message, ahora)
                await self._desactivar_correo(preference, exc.message, ahora)
            else:
                delivery.mark_sent(ahora)
                enviados += 1

            await self.delivery_repo.save(delivery)

        return enviados
