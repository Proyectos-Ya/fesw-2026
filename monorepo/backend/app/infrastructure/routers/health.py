from fastapi import APIRouter


def create_health_router() -> APIRouter:
    router = APIRouter()

    @router.get("/")
    async def root() -> dict[str, str]:
        # Mensaje de bienvenida del servicio
        return {"message": "Welcome to ProyectosYA API", "status": "online"}

    @router.get("/health")
    async def health_check() -> dict[str, str]:
        # Verificación básica del estado del servicio
        return {"status": "healthy"}

    return router
