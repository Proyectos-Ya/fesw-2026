"""Receptor de subidas del disco local, SOLO para desarrollo (plan 233, decisión 2).

Es la contraparte de la URL firmada de R2 cuando no hay credenciales: el navegador
hace `PUT` acá, directo al backend y no por `/api` (el rewrite de Next corta los
cuerpos a 10 MB). No hay sesión: lo único que autoriza la escritura es el token
HMAC de la URL, que ata la clave, el tamaño y la huella. Se monta solo sin R2 y
con `IS_DEV` (ver `bootstrap`).
"""

from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse, Response

from app.infrastructure.services.attachments.checksums import sha256_hex_a_base64
from app.infrastructure.services.attachments.local_attachment_storage import (
    ContenidoInvalido,
    LocalDiskAttachmentStorage,
)
from app.shared.datetime_utils import utc_now_naive


def _error(estado: int, codigo: str, detalle: str) -> JSONResponse:
    return JSONResponse(status_code=estado, content={"detail": detalle, "code": codigo})


def create_dev_storage_router(
    storage: LocalDiskAttachmentStorage,
    *,
    clock: Callable[[], datetime] = utc_now_naive,
) -> APIRouter:
    """Fábrica del router. Sin dependencias de sesión: el token es la autorización."""
    router = APIRouter(tags=["Dev storage"])

    @router.put(
        "/dev-storage/{key:path}",
        summary="Recibir un anexo en el disco local (solo desarrollo)",
        status_code=status.HTTP_200_OK,
        response_class=Response,
        response_model=None,
        responses={
            400: {"description": "`bad_digest` o `size_mismatch`: el cuerpo no es el firmado"},
            403: {"description": "`signature_mismatch`: token inválido o vencido"},
            411: {"description": "Falta `Content-Length`"},
        },
    )
    async def receive_upload(
        key: str, request: Request, expires: int, size: int, sha256: str, token: str
    ) -> Response:
        """Guarda el cuerpo en el disco local si coincide con lo que firmó la URL.

        Solo existe en desarrollo y sin Cloudflare R2. El cuerpo se lee por partes
        y se verifica mientras llega: nunca se carga entero en memoria.
        """
        if not storage.verificar_token(
            key=key, expires=expires, size=size, sha256_hex=sha256, token=token, now=clock()
        ):
            return _error(
                status.HTTP_403_FORBIDDEN,
                "signature_mismatch",
                "La firma de la URL no es válida o venció.",
            )
        try:
            esperado = sha256_hex_a_base64(sha256)
        except ValueError:
            esperado = None
        if esperado is None or request.headers.get("x-amz-checksum-sha256") != esperado:
            return _error(
                status.HTTP_400_BAD_REQUEST,
                "bad_digest",
                "La cabecera x-amz-checksum-sha256 no coincide con la firmada.",
            )
        largo = request.headers.get("content-length")
        if largo is None:
            return _error(
                status.HTTP_411_LENGTH_REQUIRED,
                "length_required",
                "Falta la cabecera Content-Length.",
            )
        if not largo.isdigit() or int(largo) != size:
            return _error(
                status.HTTP_400_BAD_REQUEST,
                "size_mismatch",
                "El tamaño del cuerpo no coincide con el firmado.",
            )
        try:
            await storage.escribir(key, request.stream(), size=size, sha256_hex=sha256)
        except ContenidoInvalido:
            return _error(
                status.HTTP_400_BAD_REQUEST,
                "bad_digest",
                "El contenido no coincide con la huella firmada.",
            )
        return Response(status_code=status.HTTP_200_OK)

    return router
