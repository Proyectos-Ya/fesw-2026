from fastapi import FastAPI
from sqlmodel import SQLModel
from contextlib import asynccontextmanager
from app.bootstrap import bootstrap
from app.infrastructure.middleware import register_middleware
from app.infrastructure.db import engine
from app.infrastructure.services.qdrant_service import QdrantService  
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    qdrant = QdrantService(url=settings.qdrant_url)
    await qdrant.initialize_collections()
    

    yield


def create_app() -> FastAPI:
    # Fábrica de la aplicación: registra middlewares y dependencias
    app = FastAPI(title="ProyectosYA API", lifespan=lifespan)
    register_middleware(app)
    bootstrap(app)
    return app


app = create_app()
