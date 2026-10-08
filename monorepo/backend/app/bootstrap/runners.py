"""Tareas fuera del ciclo de petición: schedulers y exportaciones en segundo plano.

No pueden apoyarse en `Depends(get_session)`: cada ejecución abre y cierra su
propia sesión."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.datastructures import State

from app.application.services.tender_refresher import ITenderRefresher
from app.application.use_cases.calendar.refresh_synced_tender_dates import (
    RefreshSyncedTenderDatesUseCase,
)
from app.application.use_cases.exports.export_jobs import (
    CompleteExportJobUseCase,
    ReconcileExportJobsUseCase,
)
from app.application.use_cases.kanban.auto_archive_old_cards import (
    AutoArchiveOldCardsUseCase,
)
from app.application.use_cases.matching.rank_tenders import RankTendersUseCase
from app.application.use_cases.milestones.extract_tender_milestones import (
    ExtractTenderMilestonesUseCase,
)
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
from app.bootstrap.calendar import build_sync_milestones_use_case
from app.bootstrap.matching import (
    build_compatibility_scorer,
    build_rank_tenders_use_case,
)
from app.bootstrap.services import build_supplier_vector_repo, build_tender_vector_repo
from app.config import settings
from app.infrastructure.db import async_session_maker
from app.infrastructure.repositories.calendar_repository import (
    CalendarConnectionRepository,
    CalendarEventLinkRepository,
)
from app.infrastructure.repositories.export_job_repository import ExportJobRepository
from app.infrastructure.repositories.kanban_repository import KanbanCardRepository
from app.infrastructure.repositories.matching_result_repository import (
    MatchingResultRepository,
)
from app.infrastructure.repositories.notification_repository import (
    NotificationDeliveryRepository,
    NotificationPreferenceRepository,
    NotificationRepository,
)
from app.infrastructure.repositories.sql_tender_chat_repository import (
    SQLTenderChatRepository,
)
from app.infrastructure.repositories.supplier_repository import SupplierRepository
from app.infrastructure.repositories.tender_milestone_document_repository import (
    TenderMilestoneDocumentRepository,
)
from app.infrastructure.repositories.tender_milestone_repository import (
    TenderMilestoneRepository,
)
from app.infrastructure.repositories.tender_repository import TenderRepository
from app.infrastructure.repositories.user_repository import UserRepository
from app.infrastructure.services.exports.background import AsyncioExportBackground
from app.infrastructure.services.milestone_extraction_background import (
    AsyncioMilestoneExtractionBackground,
)

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


def build_milestone_extraction_background(app: FastAPI) -> AsyncioMilestoneExtractionBackground:
    """Extrae los hitos de las bases apenas se suben (HU-16, criterio 1).

    Cada pasada abre su propia sesión: cuando la IA termina, la sesión de la
    subida que la originó ya se cerró.
    """

    @asynccontextmanager
    async def open_extraction():
        async with async_session_maker() as session:
            yield ExtractTenderMilestonesUseCase(
                tenders=TenderRepository(session),
                milestones=TenderMilestoneRepository(session),
                event_links=CalendarEventLinkRepository(session),
                chat=SQLTenderChatRepository(session),
                ai=app.state.milestone_extraction_service,
                processed=TenderMilestoneDocumentRepository(session),
            )

    return AsyncioMilestoneExtractionBackground(open_extraction)


async def reconcile_export_jobs() -> tuple[int, int]:
    """Al arrancar: falla lo que quedó en proceso y vacía los archivos vencidos."""
    async with async_session_maker() as session:
        return await ReconcileExportJobsUseCase(ExportJobRepository(session)).execute()


def build_kanban_archive_runner(age_days: int = 90) -> Callable[[], Awaitable[list[UUID]]]:
    """Runner diario del `KanbanArchiveScheduler` (HdU 10, CA4).

    Abre su propia sesión en cada vuelta: el bucle vive fuera del ciclo de
    petición de FastAPI, igual que el resto de runners de este archivo.
    """

    async def auto_archive() -> list[UUID]:
        async with async_session_maker() as session:
            use_case = AutoArchiveOldCardsUseCase(
                card_repo=KanbanCardRepository(session),
                age_days=age_days,
            )
            return await use_case.execute()

    return auto_archive


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
            sync = build_sync_milestones_use_case(
                tenders=tenders,
                milestones=milestones,
                connections=CalendarConnectionRepository(session, app.state.token_cipher),
                event_links=event_links,
                providers=app.state.calendar_providers,
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


def build_scan_rank_tenders_use_case(
    state: State, session: AsyncSession
) -> RankTendersUseCase:
    """El ranking que usa el escaneo de alertas, armado con la sesión de la vuelta.

    Usa el mismo constructor que el provider de la API: antes era una copia
    aparte y se quedó sin el servicio de embeddings cuando la API lo sumó.
    """
    matching_results = MatchingResultRepository(session)
    return build_rank_tenders_use_case(
        supplier_repo=SupplierRepository(session),
        supplier_vector_repo=build_supplier_vector_repo(state),
        tender_vector_repo=build_tender_vector_repo(state),
        tender_repo=TenderRepository(session),
        scorer=build_compatibility_scorer(
            reranker_service=state.reranker_service,
            weighting_service=state.weighting_service,
            matching_result_repo=matching_results,
        ),
        matching_result_repo=matching_results,
        embedding_service=state.embedding_service,
    )


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

    async def scan_all() -> int:
        async with async_session_maker() as session:
            user_ids = await SupplierRepository(session).list_user_ids_with_profile()

        total = 0
        for user_id in user_ids:
            try:
                async with async_session_maker() as session:
                    use_case = ScanSupplierForAlertsUseCase(
                        rank_tenders_use_case=build_scan_rank_tenders_use_case(
                            app.state, session
                        ),
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
