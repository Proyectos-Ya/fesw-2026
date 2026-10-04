"""Tareas fuera del ciclo de petición: schedulers y exportaciones en segundo plano.

No pueden apoyarse en `Depends(get_session)`: cada ejecución abre y cierra su
propia sesión."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.services.compatibility_scorer import CompatibilityScorer
from app.application.services.tender_refresher import ITenderRefresher
from app.application.use_cases.calendar.refresh_synced_tender_dates import (
    RefreshSyncedTenderDatesUseCase,
)
from app.application.use_cases.calendar.sync_milestones import (
    SyncMilestonesToCalendarUseCase,
)
from app.application.use_cases.exports.export_jobs import (
    CompleteExportJobUseCase,
    ReconcileExportJobsUseCase,
)
from app.application.use_cases.matching.rank_tenders import RankTendersUseCase
from app.application.use_cases.milestones.send_milestone_reminders import (
    SendMilestoneRemindersUseCase,
)
from app.application.use_cases.notifications.build_daily_digest import (
    BuildDailyDigestUseCase,
)
from app.application.use_cases.notifications.dispatch_pending_deliveries import (
    DispatchPendingDeliveriesUseCase,
)
from app.application.use_cases.notifications.scan_supplier_for_alerts import (
    ScanSupplierForAlertsUseCase,
)
from app.config import settings
from app.infrastructure.db import async_session_maker
from app.infrastructure.repositories.calendar_repository import (
    CalendarConnectionRepository,
    CalendarEventLinkRepository,
)
from app.infrastructure.repositories.export_job_repository import ExportJobRepository
from app.infrastructure.repositories.matching_result_repository import (
    MatchingResultRepository,
)
from app.infrastructure.repositories.notification_repository import (
    NotificationDeliveryRepository,
    NotificationPreferenceRepository,
    NotificationRepository,
)
from app.infrastructure.repositories.qdrant_supplier_repository import (
    QdrantSupplierRepository,
)
from app.infrastructure.repositories.qdrant_tender_repository import (
    QdrantTenderRepository,
)
from app.infrastructure.repositories.supplier_repository import SupplierRepository
from app.infrastructure.repositories.tender_milestone_repository import (
    TenderMilestoneRepository,
)
from app.infrastructure.repositories.tender_repository import TenderRepository
from app.infrastructure.repositories.user_repository import UserRepository
from app.infrastructure.services.exports.background import AsyncioExportBackground

logger = logging.getLogger(__name__)


def build_export_background(app: FastAPI) -> AsyncioExportBackground:
    """Termina las exportaciones que pasaron a segundo plano.

    Cada trabajo abre su propia sesión: cuando la generación termina, la sesión
    de la petición que lo originó ya se cerró.
    """

    @asynccontextmanager
    async def open_completion():
        async with async_session_maker() as session:
            yield CompleteExportJobUseCase(
                jobs=ExportJobRepository(session),
                email=app.state.email_service,
                base_url=settings.app_base_url,
            )

    return AsyncioExportBackground(open_completion)


async def reconcile_export_jobs() -> tuple[int, int]:
    """Al arrancar: falla lo que quedó en proceso y vacía los archivos vencidos."""
    async with async_session_maker() as session:
        return await ReconcileExportJobsUseCase(ExportJobRepository(session)).execute()


def build_milestone_refresh_runner(
    app: FastAPI, refresher: ITenderRefresher
) -> Callable[[], Awaitable[int]]:
    """Arma la función que ejecuta `MilestoneRefreshScheduler` (HU-16).

    Como los runners de alertas, abre su propia sesión en cada vuelta: vive
    fuera del ciclo de petición de FastAPI.
    """

    async def refresh() -> int:
        async with async_session_maker() as session:
            tenders = TenderRepository(session)
            milestones = TenderMilestoneRepository(session)
            event_links = CalendarEventLinkRepository(session)
            sync = SyncMilestonesToCalendarUseCase(
                tenders=tenders,
                milestones=milestones,
                connections=CalendarConnectionRepository(session, app.state.token_cipher),
                event_links=event_links,
                providers=app.state.calendar_providers,
                app_base_url=settings.app_base_url,
            )
            return await RefreshSyncedTenderDatesUseCase(
                tenders=tenders,
                refresher=refresher,
                milestones=milestones,
                event_links=event_links,
                sync=sync,
                notifications=NotificationRepository(session),
                deliveries=NotificationDeliveryRepository(session),
                preferences=NotificationPreferenceRepository(session),
            ).execute()

    return refresh


def build_notification_runners(
    app: FastAPI,
) -> tuple[
    Callable[[], Awaitable[int]],
    Callable[[], Awaitable[int]],
    Callable[[], Awaitable[int]],
    Callable[[], Awaitable[int]],
]:
    """Arma las cuatro funciones que ejecuta `NotificationScheduler`.

    Los bucles viven fuera del ciclo de petición de FastAPI, así que no pueden
    apoyarse en `Depends(get_session)`: cada ejecución abre y cierra su propia
    sesión. Se hace acá, en el composition root, para que el scheduler no
    conozca ningún repositorio concreto.
    """

    def _rank_tenders(session: AsyncSession) -> RankTendersUseCase:
        return RankTendersUseCase(
            supplier_repo=SupplierRepository(session),
            supplier_vector_repo=QdrantSupplierRepository(app.state.qdrant_async_client),
            tender_vector_repo=QdrantTenderRepository(
                client=app.state.qdrant_async_client,
                vector_size=settings.embedding_vector_size,
            ),
            tender_repo=TenderRepository(session),
            scorer=CompatibilityScorer(
                reranker_service=app.state.reranker_service,
                weighting_service=app.state.weighting_service,
                matching_result_repo=MatchingResultRepository(session),
                model_version=settings.embedding_model,
            ),
            matching_result_repo=MatchingResultRepository(session),
            model_version=settings.embedding_model,
        )

    async def scan_all() -> int:
        async with async_session_maker() as session:
            user_ids = await SupplierRepository(session).list_user_ids_with_profile()

        total = 0
        for user_id in user_ids:
            try:
                async with async_session_maker() as session:
                    use_case = ScanSupplierForAlertsUseCase(
                        rank_tenders_use_case=_rank_tenders(session),
                        preference_repo=NotificationPreferenceRepository(session),
                        notification_repo=NotificationRepository(session),
                        delivery_repo=NotificationDeliveryRepository(session),
                    )
                    total += len(await use_case.execute(user_id))
            except Exception as e:
                # Un proveedor sin vector en Qdrant, o cualquier otro fallo
                # puntual, no puede detener el escaneo del resto.
                logger.warning("No se pudo escanear al usuario %s: %s", user_id, e)

            # El reranker es CPU y la API corre con un solo worker: sin esta
            # pausa, un escaneo largo dejaría las peticiones esperando.
            await asyncio.sleep(1)
        return total

    async def dispatch_pending() -> int:
        async with async_session_maker() as session:
            use_case = DispatchPendingDeliveriesUseCase(
                delivery_repo=NotificationDeliveryRepository(session),
                notification_repo=NotificationRepository(session),
                preference_repo=NotificationPreferenceRepository(session),
                user_repo=UserRepository(session),
                tender_repo=TenderRepository(session),
                email_service=app.state.email_service,
                base_url=settings.app_base_url,
            )
            return await use_case.execute()

    async def build_digest() -> int:
        async with async_session_maker() as session:
            use_case = BuildDailyDigestUseCase(
                preference_repo=NotificationPreferenceRepository(session),
                notification_repo=NotificationRepository(session),
                delivery_repo=NotificationDeliveryRepository(session),
            )
            return await use_case.execute()

    async def send_milestone_reminders() -> int:
        async with async_session_maker() as session:
            use_case = SendMilestoneRemindersUseCase(
                tenders=TenderRepository(session),
                milestones=TenderMilestoneRepository(session),
                notifications=NotificationRepository(session),
                deliveries=NotificationDeliveryRepository(session),
                preferences=NotificationPreferenceRepository(session),
            )
            return await use_case.execute()

    return scan_all, dispatch_pending, build_digest, send_milestone_reminders
