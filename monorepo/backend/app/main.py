from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.models import VectorParams, Distance

from app.infrastructure.services.tenders.mercado_publico_client import MercadoPublicoClient
from app.infrastructure.services.tenders.tender_scheduler import TenderScheduler

from app.bootstrap import bootstrap
from app.config import settings
from app.infrastructure.db import engine
from app.infrastructure.seeder import seed_database_metadata
from app.infrastructure.middleware import register_middleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    app.state.qdrant_client = QdrantClient(url=settings.qdrant_url)
    app.state.qdrant_async_client = AsyncQdrantClient(url=settings.qdrant_url)

    async with AsyncSession(engine) as session:
        await seed_database_metadata(session)

    app.state.qdrant_client.recreate_collection(
        collection_name="suppliers",
        vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
    )
    app.state.qdrant_client.recreate_collection(
        collection_name="tenders",
        vectors_config={
            "tender": VectorParams(size=1024, distance=Distance.COSINE)
        },
    )

    ingestion_service = MercadoPublicoClient(api_key=settings.mercado_publico_api_key)
    scheduler = TenderScheduler(engine, ingestion_service, is_dev=settings.is_dev)
    print("[Main] Iniciando scheduler de ingesta...")
    ingestion_task = asyncio.create_task(scheduler.start_periodic_ingestion())
    yield

    ingestion_task.cancel()
    app.state.qdrant_client.close()
    await app.state.qdrant_async_client.close()


def create_app() -> FastAPI:
    # Fábrica de la aplicación: registra middlewares y dependencias
    app = FastAPI(title="ProyectosYA API", lifespan=lifespan)
    register_middleware(app)
    bootstrap(app)
    return app


app = create_app()
