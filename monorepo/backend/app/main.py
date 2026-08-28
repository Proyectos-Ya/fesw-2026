import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client.models import Distance, VectorParams
from sqlmodel.ext.asyncio.session import AsyncSession

from app.bootstrap import bootstrap, build_notification_runners
from app.config import settings
from app.infrastructure.db import engine, verificar_esquema_migrado
from app.infrastructure.middleware import register_middleware
from app.infrastructure.repositories.qdrant_tender_repository import (
    QdrantTenderRepository,
)
from app.infrastructure.seeder import seed_database_metadata
from app.infrastructure.services.notifications.notification_scheduler import (
    NotificationScheduler,
)
from app.infrastructure.services.tenders.mercado_publico_client import (
    MercadoPublicoClient,
)
from app.infrastructure.services.tenders.tender_ingestion_service import (
    TenderIngestionService,
)
from app.infrastructure.services.tenders.tender_scheduler import TenderScheduler


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
    app.state.qdrant_client = QdrantClient(
        url=settings.qdrant_url, api_key=settings.qdrant_api_key
    )
    app.state.qdrant_async_client = AsyncQdrantClient(
        url=settings.qdrant_url, api_key=settings.qdrant_api_key
    )

    async with AsyncSession(engine) as session:
        await seed_database_metadata(session)

    existing = {c.name for c in app.state.qdrant_client.get_collections().collections}
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

    client = MercadoPublicoClient(api_key=settings.mercado_publico_api_key)
    ingestion_service = TenderIngestionService(
        engine=engine,
        client=client,
        embedding_service=app.state.embedding_service,
        qdrant_client=app.state.qdrant_async_client,
    )
    scheduler = TenderScheduler(ingestion_service=ingestion_service)
    metadata_task = None
    processing_task = None
    if settings.run_auto_ingestion:
        print("[Main] Iniciando tareas en segundo plano de ingesta de licitaciones...")
        metadata_task = asyncio.create_task(scheduler.start_metadata_loop())
        processing_task = asyncio.create_task(scheduler.start_processing_loop())
    else:
        print(
            "[Main] Ingesta automática desactivada (RUN_AUTO_INGESTION=false). Usando modo offline / mock local."
        )

    # Alertas de licitaciones (HdU 08). Van aparte de la ingesta: el corpus
    # puede venir de un dump y aun así hay que avisar de lo que ya está en la
    # base, así que este bucle no depende de RUN_AUTO_INGESTION.
    scan_task = None
    delivery_task = None
    digest_task = None
    if settings.run_notification_scan:
        scan_all, dispatch_pending, build_digest = build_notification_runners(app)
        notification_scheduler = NotificationScheduler(
            scan_all=scan_all,
            dispatch_pending=dispatch_pending,
            build_digest=build_digest,
            scan_interval_seconds=settings.notification_scan_interval_seconds,
            digest_hour=settings.notification_digest_hour,
        )
        print("[Main] Iniciando tareas en segundo plano de alertas...")
        scan_task = asyncio.create_task(notification_scheduler.start_scan_loop())
        delivery_task = asyncio.create_task(
            notification_scheduler.start_delivery_loop()
        )
        digest_task = asyncio.create_task(notification_scheduler.start_digest_loop())
    else:
        print("[Main] Alertas desactivadas (RUN_NOTIFICATION_SCAN=false)")

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
        for t in (metadata_task, processing_task, scan_task, delivery_task, digest_task)
        if t
    ]
    for tarea in tareas:
        tarea.cancel()
    if tareas:
        await asyncio.gather(*tareas, return_exceptions=True)

    app.state.qdrant_client.close()
    await app.state.qdrant_async_client.close()


def create_app() -> FastAPI:
    # Fábrica de la aplicación: registra middlewares y dependencias
    app = FastAPI(title="ProyectosYA API", lifespan=lifespan)
    register_middleware(app)
    bootstrap(app)
    return app


app = create_app()
