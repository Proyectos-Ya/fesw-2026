from uuid import UUID

from app.application.repositories.notification_repository import (
    INotificationDeliveryRepository,
    INotificationPreferenceRepository,
    INotificationRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.use_cases.matching.rank_tenders import RankTendersUseCase
from app.domain.entities.notification import (
    Notification,
    NotificationDelivery,
    NotificationPreference,
)


class ScanSupplierForAlertsUseCase:
    """Detecta licitaciones compatibles nuevas para un proveedor y las avisa.

    Es el corazón de la HdU 08. Se ejecuta desde el scheduler, sin petición HTTP
    de por medio: el usuario no tiene que entrar a la plataforma para que esto
    ocurra.

    HU-18: la resolución del umbral de match es jerárquica:
    1. Si `supplier.match_threshold` no es None, se usa ese valor para todos
       los miembros del workspace.
    2. Si no, se cae al `preference.threshold` del usuario individual.
    """

    def __init__(
        self,
        rank_tenders_use_case: RankTendersUseCase,
        preference_repo: INotificationPreferenceRepository,
        notification_repo: INotificationRepository,
        delivery_repo: INotificationDeliveryRepository,
        supplier_repo: ISupplierRepository | None = None,
    ) -> None:
        self.rank_tenders_use_case = rank_tenders_use_case
        self.preference_repo = preference_repo
        self.notification_repo = notification_repo
        self.delivery_repo = delivery_repo
        self.supplier_repo = supplier_repo

    async def execute(
        self, user_id: UUID, supplier_id: UUID | None = None
    ) -> list[Notification]:
        preference = await self.preference_repo.get_by_user_id(user_id)
        if preference is None:
            # Sin fila guardada valen los defaults del dominio (activadas, 70%).
            # No se persiste acá: la fila se crea cuando el usuario abre sus
            # preferencias o las cambia.
            preference = NotificationPreference(user_id=user_id)

        if not preference.enabled:
            return []

        threshold = await self._resolve_threshold(preference, supplier_id)

        matches = await self.rank_tenders_use_case.execute(user_id)
        if not matches:
            return []

        # El registro de lo ya avisado es lo que evita repetir el mismo aviso en
        # cada ciclo del scheduler.
        ya_avisadas = await self.notification_repo.get_notified_tender_ids(user_id)

        nuevos = [
            Notification(
                user_id=user_id,
                tender_id=match.tender_id,
                score=match.final_score,
            )
            for match in matches
            if match.final_score is not None
            and match.final_score >= threshold
            and match.tender_id not in ya_avisadas
        ]
        if not nuevos:
            return []

        await self.notification_repo.save_bulk(nuevos)

        # En modo inmediato sale un solo correo con todo lo detectado en este
        # ciclo. Uno por licitación llenaría la bandeja del usuario cuando la
        # ingesta trae varias de golpe.
        if preference.delivery_mode == "immediate" and preference.wants_email():
            await self.delivery_repo.save(
                NotificationDelivery(
                    user_id=user_id,
                    kind="immediate",
                    notification_ids=[n.id for n in nuevos],
                )
            )

        return nuevos

    async def _resolve_threshold(
        self, preference: NotificationPreference, supplier_id: UUID | None
    ) -> float:
        # Fallback a preferencia individual si no hay workspace o no hay repo.
        if supplier_id is None or self.supplier_repo is None:
            return preference.threshold
        supplier = await self.supplier_repo.get_by_id(supplier_id)
        if supplier is None or supplier.match_threshold is None:
            return preference.threshold
        return supplier.match_threshold
