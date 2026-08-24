import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.config import settings

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Loguea cada request: método, ruta, status y tiempo de respuesta."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Registra el request entrante
        start_time = time.perf_counter()
        logger.info(f"→ {request.method} {request.url.path}")

        response = await call_next(request)

        # Registra el response con el tiempo que tardó
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"← {response.status_code} {request.url.path} ({duration_ms:.1f}ms)"
        )

        return response


class CookieCleanupMiddleware(BaseHTTPMiddleware):
    """Limpia la cookie de sesión si el backend responde con 401 Unauthorized."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        # Si la respuesta es 401 y el cliente envió la cookie, la borramos para evitar bucles de redirección
        from app.config import settings

        cookie_name = settings.auth_cookie_name
        if response.status_code == 401 and request.cookies.get(cookie_name):
            response.delete_cookie(
                key=cookie_name,
                path="/",
                secure=bool(settings.auth_cookie_secure),
                samesite=settings.auth_cookie_samesite,
            )
        return response


def register_middleware(app: FastAPI) -> None:
    """Registra todos los middlewares de la aplicación en orden."""

    # CORS — orígenes desde configuración (CORS_ORIGINS, separados por coma).
    # Nunca "*": con allow_credentials=True el navegador rechaza el comodín, y
    # aunque lo aceptara sería abrir la API con cookies a cualquier sitio.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Cookie Cleanup — limpia cookies inválidas de sesión
    app.add_middleware(CookieCleanupMiddleware)

    # Logging — loguea todos los requests
    app.add_middleware(LoggingMiddleware)
