from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import licitaciones, matching, proveedores

app = FastAPI(
    title="ProyectosYA API",
    description="Backend API for ProyectosYA - Bidding matching platform",
    version="0.1.0",
)

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


app.include_router(proveedores.router)
app.include_router(licitaciones.router)
app.include_router(matching.router)
