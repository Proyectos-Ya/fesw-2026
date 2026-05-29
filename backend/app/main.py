from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.database import create_db_and_tables
from app.providers.models.proveedor import Proveedor 


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}