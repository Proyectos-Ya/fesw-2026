from fastapi import FastAPI
<<<<<<< HEAD
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel
=======
>>>>>>> parent of c4700ad (Merge branch 'develop' into feat/login)
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
from contextlib import asynccontextmanager
from app.bootstrap import bootstrap
<<<<<<< HEAD
from app.infrastructure.middleware import register_middleware
from app.infrastructure.db import engine
from app.config import settings
from app.routers import licitaciones, matching, proveedores
=======
from app.config import settings
from app.infrastructure.db import engine
from app.infrastructure.middleware import register_middleware
>>>>>>> parent of c4700ad (Merge branch 'develop' into feat/login)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    app.state.qdrant_client = QdrantClient(url=settings.qdrant_url)

    app.state.qdrant_client.recreate_collection(
        collection_name="suppliers",
        vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
    )

    yield

    app.state.qdrant_client.close()


def create_app() -> FastAPI:
    # Fábrica de la aplicación: registra middlewares y dependencias
    app = FastAPI(title="ProyectosYA API", lifespan=lifespan)
    register_middleware(app)
    bootstrap(app)
    return app


app = create_app()
