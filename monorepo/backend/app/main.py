from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from sqlmodel import SQLModel

from app.bootstrap import bootstrap
from app.config import settings
from app.infrastructure.db import engine
from app.infrastructure.middleware import register_middleware
# from app.routers import licitaciones, matching


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    app.state.qdrant_client = QdrantClient(url=settings.qdrant_url)

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


    yield

    app.state.qdrant_client.close()


def create_app() -> FastAPI:
    # Fábrica de la aplicación: registra middlewares y dependencias
    app = FastAPI(title="ProyectosYA API", lifespan=lifespan)
    register_middleware(app)
    bootstrap(app)
    return app


app = create_app()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "Welcome to ProyectosYA API",
        "version": "0.1.0",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


app.include_router(licitaciones.router)
app.include_router(matching.router)

