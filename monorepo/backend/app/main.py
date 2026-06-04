from fastapi import FastAPI
from sqlmodel import SQLModel
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
from contextlib import asynccontextmanager
import asyncio

# Imports de tenders
from app.infrastructure.services.tenders.mercado_publico_client import MercadoPublicoClient
from app.infrastructure.repositories.mock_tenders_repository import MockTendersRepository
from app.application.use_cases.tender_ingestion_use_case import TenderIngestionUseCase
from app.infrastructure.services.tenders.tender_scheduler import TenderScheduler

from app.bootstrap import bootstrap
from app.infrastructure.middleware import register_middleware
from app.infrastructure.db import engine
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    app.state.qdrant_client = QdrantClient(url=settings.qdrant_url)

    app.state.qdrant_client.recreate_collection(
        collection_name="suppliers",
        vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
    )

    # Instancia las dependencias con el .env
    ingestion_service = MercadoPublicoClient(api_key=settings.mercado_publico_api_key)
    repository = MockTendersRepository()
    use_case = TenderIngestionUseCase(ingestion_service, repository)

    # Sheduler
    scheduler = TenderScheduler(use_case, is_dev=settings.is_dev)
    # Mantenemos el scheduler como tarea de fondo, sin detener el arranque de la API
    ingestion_task = asyncio.create_task(scheduler.start_periodic_ingestion())

    yield

    ingestion_task.cancel()
    app.state.qdrant_client.close()


def create_app() -> FastAPI:
    # Fábrica de la aplicación: registra middlewares y dependencias
    app = FastAPI(title="ProyectosYA API", lifespan=lifespan)
    register_middleware(app)
    bootstrap(app)
    return app


app = create_app()
