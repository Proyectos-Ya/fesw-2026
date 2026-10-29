import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client.models import Distance, VectorParams
from sqlmodel.ext.asyncio.session import AsyncSession

from app.bootstrap import bootstrap
from app.bootstrap.runners import (
    build_attachment_processing_runner,
    build_kanban_archive_runner,
    build_milestone_refresh_runner,
    build_notification_runners,
    build_ranking_telemetry_runner,
    reconcile_export_jobs,
)
from app.config import settings
from app.infrastructure.db import engine, verificar_esquema_migrado
from app.infrastructure.middleware import register_middleware
from app.infrastructure.repositories.qdrant_tender_item_vector_repository import (
    QdrantTenderItemVectorRepository,
)
from app.infrastructure.repositories.qdrant_tender_repository import (
    QdrantTenderRepository,
)
from app.infrastructure.seeder import seed_database_metadata
from app.infrastructure.services.attachment_processing_scheduler import (
    AttachmentProcessingScheduler,
)
from app.infrastructure.services.kanban.archive_scheduler import (
    KanbanArchiveScheduler,
)
from app.infrastructure.services.milestone_refresh_scheduler import (
    MilestoneRefreshScheduler,
)
from app.infrastructure.services.notifications.notification_scheduler import (
    NotificationScheduler,
)
from app.infrastructure.services.ranking_telemetry_scheduler import (
    RankingTelemetryScheduler,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # El esquema ya NO se crea acá. Antes esto era `SQLModel.metadata.create_all`,
    # con dos problemas: `create_all` agrega las tablas que faltan pero **no
    # altera las existentes**, así que cualquier columna o restricción nueva
    # quedaba fuera en silencio; y con dos réplicas arrancando a la vez, ambas
    # intentaban crear el esquema al mismo tiempo.
    #
    # Ahora lo hace Alembic, como paso previo y explícito:
    #     alembic upgrade head
    # Verificamos que se haya corrido para fallar acá, con un mensaje claro, en
    # vez de más adelante con un error de "relation does not exist".
    await verificar_esquema_migrado()

    # api_key va en None contra el Qdrant del compose local, que no autentica.
    try:
        app.state.qdrant_client = QdrantClient(
            url=settings.qdrant_url, api_key=settings.qdrant_api_key, timeout=30.0
        )
        app.state.qdrant_async_client = AsyncQdrantClient(
            url=settings.qdrant_url, api_key=settings.qdrant_api_key, timeout=30.0
        )
        existing = {c.name for c in app.state.qdrant_client.get_collections().collections}
    except Exception as e:
        if settings.is_dev:
            print(f"[Main] Qdrant no disponible ({e}), usando cliente en memoria para desarrollo.")
            app.state.qdrant_client = QdrantClient(location=":memory:")
            app.state.qdrant_async_client = AsyncQdrantClient(location=":memory:")
            existing = set()
        else:
            raise

    async with AsyncSession(engine) as session:
        await seed_database_metadata(session)

    # Exportaciones en segundo plano (HdU 19): viven en la memoria del proceso,
    # así que las que quedaron a medias antes de este arranque ya no terminarán.
    colgadas, purgadas = await reconcile_export_jobs()
    if colgadas or purgadas:
        print(f"[Main] Exportaciones: {colgadas} interrumpidas, {purgadas} vencidas limpiadas")

    if "suppliers" not in existing:
        app.state.qdrant_client.create_collection(
            collection_name="suppliers",
            vectors_config=VectorParams(
                size=settings.embedding_vector_size, distance=Distance.COSINE
            ),
        )

    # La colección de licitaciones se delega al repositorio en vez de crearse
    # inline: además de la colección, `ensure_collection` crea los índices de
    # payload que el pre-filtrado del buscador necesita. Creándola aquí a mano,
    # esos índices no existirían nunca en un entorno real.
    await QdrantTenderRepository(
        client=app.state.qdrant_async_client,
        vector_size=settings.embedding_vector_size,
    ).ensure_collection()

    # Colección aparte con un multivector por licitación (un vector por partida),
    # para el calce de keywords contra cada ítem. No se agrega a "tenders" porque
    # un vector nombrado nuevo obligaría a recrear esa colección.
    await QdrantTenderItemVectorRepository(
        client=app.state.qdrant_async_client,
        vector_size=settings.embedding_vector_size,
    ).ensure_collection()

    # La ingesta de licitaciones NO corre acá. Vivía en este lifespan como dos
    # bucles (`TenderScheduler`), y competía por la cola y la cuota del ticket con
    # el cron `scripts/sync_diaria.py`, que es quien la hace ahora.

    # Alertas de licitaciones (HdU 08). Leen lo que ya está en la base, venga del
    # cron o de un dump local.
    scan_task = None
    delivery_task = None
    digest_task = None
    reminder_task = None
    if settings.run_notification_scan:
        scan_all, dispatch_pending, build_digest, send_reminders = (
            build_notification_runners(app)
        )
        notification_scheduler = NotificationScheduler(
            scan_all=scan_all,
            dispatch_pending=dispatch_pending,
            build_digest=build_digest,
            send_milestone_reminders=send_reminders,
            scan_interval_seconds=settings.notification_scan_interval_seconds,
            digest_hour=settings.notification_digest_hour,
        )
        print("[Main] Iniciando tareas en segundo plano de alertas...")
        scan_task = asyncio.create_task(notification_scheduler.start_scan_loop())
        delivery_task = asyncio.create_task(
            notification_scheduler.start_delivery_loop()
        )
        digest_task = asyncio.create_task(notification_scheduler.start_digest_loop())
        reminder_task = asyncio.create_task(notification_scheduler.start_reminder_loop())
    else:
        print("[Main] Alertas desactivadas (RUN_NOTIFICATION_SCAN=false)")

    # Cambios de fecha en licitaciones sincronizadas con un calendario (HU-16).
    # Sin Google Calendar configurado no hay nada sincronizado que revisar.
    #
    # Arma su propio `TenderIngestionService` en vez de reusar el de la ingesta,
    # que ya no vive acá (ver arriba). No compite con el cron: no toca la cola
    # `tender_metadata`, solo pide el detalle de las licitaciones que alguien
    # tiene sincronizadas y siguen abiertas, que son unas pocas por vuelta.
    # Auto-archivado del Kanban (HdU 10, CA4). Barrido diario que marca como
    # `auto_3m` todo lo que lleve más de 90 días en el tablero sin tocarse.
    kanban_archive_task = None
    if getattr(settings, "run_kanban_auto_archive", True):
        kanban_archive_scheduler = KanbanArchiveScheduler(
            auto_archive=build_kanban_archive_runner(age_days=90),
        )
        print("[Main] Iniciando auto-archivado del tablero Kanban...")
        kanban_archive_task = asyncio.create_task(
            kanban_archive_scheduler.start_loop()
        )

    milestone_refresh_task = None
    if settings.run_milestone_refresh and app.state.calendar_providers:
        # Sin refresher (plan 305): compara los hitos con las fechas que el cron
        # de estados ya escribe cada hora en `tender`, sin gastar cuota de
        # Mercado Público desde el proceso de la API.
        milestone_scheduler = MilestoneRefreshScheduler(
            refresh=build_milestone_refresh_runner(app, None),
            interval_seconds=settings.milestone_refresh_interval_seconds,
        )
        print("[Main] Iniciando revisión de cambios de fechas de hitos...")
        milestone_refresh_task = asyncio.create_task(milestone_scheduler.start_loop())

    # Telemetría del ranking (plan 233, decisión 8). Mismo supuesto de una sola
    # instancia; con dos, los upserts y la purga quedan idempotentes y solo se
    # duplica algún snapshot.
    ranking_telemetry_task = None
    if settings.run_ranking_telemetry_jobs:
        ranking_telemetry_scheduler = RankingTelemetryScheduler(
            run_cycle=build_ranking_telemetry_runner(),
            interval_seconds=settings.ranking_telemetry_interval_seconds,
        )
        print(
            "[Main] Iniciando telemetría del ranking "
            "(NDCG diario, prioridad en sombra, purga)..."
        )
        ranking_telemetry_task = asyncio.create_task(
            ranking_telemetry_scheduler.start_loop()
        )

    # Extracción de anexos con Gemini y resumen (plan 233, decisión 4). Apagado por
    # defecto porque cuesta: lo subido igual queda en cola y se procesa al encender.
    attachment_processing_task = None
    if settings.run_attachment_processing:
        if app.state.attachment_storage is None:
            print(
                "[Main] Procesamiento de anexos sin almacenamiento configurado: no se inicia."
            )
        else:
            process_next, sweep = build_attachment_processing_runner(app)
            attachment_scheduler = AttachmentProcessingScheduler(
                process_next=process_next,
                sweep=sweep,
                signal=app.state.attachment_processing_signal,
                poll_interval_seconds=settings.attachment_processing_poll_seconds,
                sweep_interval_seconds=settings.attachment_processing_sweep_seconds,
            )
            print(
                "[Main] Iniciando el procesamiento de anexos (Gemini, "
                f"tope {settings.attachment_gemini_daily_budget} llamadas/día)..."
            )
            attachment_processing_task = asyncio.create_task(
                attachment_scheduler.start_loop()
            )
    else:
        print(
            "[Main] Procesamiento de anexos desactivado (RUN_ATTACHMENT_PROCESSING=false)"
        )

    yield

    # `cancel()` solo *pide* la cancelación: marca la tarea y devuelve el control
    # de inmediato. Sin esperarlas, el proceso seguía apagándose mientras los
    # bucles todavía estaban dentro de una consulta, y en producción el SIGTERM
    # del despliegue cortaba transacciones a medias. `gather` con
    # return_exceptions=True espera a que cada una termine de propagar su
    # CancelledError, y no se traga nada porque justamente esa excepción es el
    # resultado esperado aquí.
    tareas = [
        t
        for t in (
            scan_task,
            delivery_task,
            digest_task,
            reminder_task,
            milestone_refresh_task,
            ranking_telemetry_task,
            attachment_processing_task,
            kanban_archive_task,
        )
        if t
    ]
    for tarea in tareas:
        tarea.cancel()
    if tareas:
        await asyncio.gather(*tareas, return_exceptions=True)
    await app.state.export_background.shutdown()
    await app.state.milestone_extraction_background.shutdown()
    await app.state.tender_analysis_background.shutdown()

    app.state.qdrant_client.close()
    await app.state.qdrant_async_client.close()


def create_app() -> FastAPI:
    # Fábrica de la aplicación: registra middlewares y dependencias
    app = FastAPI(title="ProyectosYA API", lifespan=lifespan)
    register_middleware(app)
    bootstrap(app)
    return app


app = create_app()
