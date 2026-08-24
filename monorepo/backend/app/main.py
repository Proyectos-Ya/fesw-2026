import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client.models import Distance, VectorParams
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.bootstrap import bootstrap
from app.config import settings
from app.infrastructure.db import engine
from app.infrastructure.middleware import register_middleware
from app.infrastructure.repositories.qdrant_tender_repository import (
    QdrantTenderRepository,
)
from app.infrastructure.seeder import seed_database_metadata
from app.infrastructure.services.tenders.mercado_publico_client import (
    MercadoPublicoClient,
)
from app.infrastructure.services.tenders.tender_ingestion_service import (
    TenderIngestionService,
)
from app.infrastructure.services.tenders.tender_scheduler import TenderScheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    app.state.qdrant_client = QdrantClient(url=settings.qdrant_url)
    app.state.qdrant_async_client = AsyncQdrantClient(url=settings.qdrant_url)

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
        print("[Main] Ingesta automática desactivada (RUN_AUTO_INGESTION=false). Usando modo offline / mock local.")

    yield

    if metadata_task:
        metadata_task.cancel()
    if processing_task:
        processing_task.cancel()
    app.state.qdrant_client.close()
    await app.state.qdrant_async_client.close()


def create_app() -> FastAPI:
    # Fábrica de la aplicación: registra middlewares y dependencias
    app = FastAPI(title="ProyectosYA API", lifespan=lifespan)
    register_middleware(app)
    bootstrap(app)
    return app


app = create_app()
