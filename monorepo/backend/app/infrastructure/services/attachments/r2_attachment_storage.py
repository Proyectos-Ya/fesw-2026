"""Almacenamiento de anexos en Cloudflare R2 (plan 233, decisión 2).

R2 habla la API de S3 con firma SigV4, region `auto` y direccionamiento por ruta
(`https://<cuenta>.r2.cloudflarestorage.com/<bucket>/<clave>`). El navegador sube
directo con una URL prefirmada; el backend solo firma, consulta (HEAD), lee, copia
y borra. **Nunca se registra la URL prefirmada, las claves ni el secreto**: la URL
lleva la firma, que es una credencial por 15 minutos.
"""

import hashlib
from collections.abc import Callable
from datetime import datetime, timedelta

import httpx

from app.application.services.attachment_storage import (
    AttachmentStorageError,
    IAttachmentStorage,
    PresignedUpload,
    StoredObjectInfo,
)
from app.infrastructure.services.attachments.checksums import (
    base64_a_sha256_hex,
    sha256_hex_a_base64,
)
from app.infrastructure.services.attachments.sigv4 import (
    SigV4Credentials,
    presign_url,
    sign_request_headers,
    uri_encode,
)
from app.shared.datetime_utils import utc_now_naive


class R2AttachmentStorage(IAttachmentStorage):
    def __init__(
        self,
        *,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        timeout_seconds: float = 30.0,
        clock: Callable[[], datetime] = utc_now_naive,
    ) -> None:
        self._host = f"{account_id}.r2.cloudflarestorage.com"
        self._bucket = bucket
        self._credentials = SigV4Credentials(access_key_id, secret_access_key, "auto")
        self._timeout = timeout_seconds
        self._clock = clock

    def _ruta(self, key: str) -> str:
        return f"/{uri_encode(self._bucket)}/{uri_encode(key, encode_slash=False)}"

    def presign_put(
        self,
        *,
        key: str,
        size_bytes: int,
        sha256_hex: str,
        content_type: str,
        expires_in_seconds: int,
        now: datetime,
    ) -> PresignedUpload:
        # Content-Length y el checksum van firmados: atan la URL al tamaño y al
        # contenido declarados sin depender de que R2 valide el checksum después.
        checksum = sha256_hex_a_base64(sha256_hex)
        url = presign_url(
            credentials=self._credentials,
            method="PUT",
            host=self._host,
            canonical_uri=self._ruta(key),
            signed_headers={
                "content-length": str(size_bytes),
                "x-amz-checksum-sha256": checksum,
            },
            expires_in_seconds=expires_in_seconds,
            now=now,
        )
        return PresignedUpload(
            url=url,
            method="PUT",
            # Sin Content-Length: es una cabecera prohibida en el navegador, que la
            # pone sola con el tamaño real del cuerpo.
            headers={"x-amz-checksum-sha256": checksum, "Content-Type": content_type},
            expires_at=now + timedelta(seconds=expires_in_seconds),
        )

    async def _pedir(
        self,
        method: str,
        key: str,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
    ) -> httpx.Response:
        firmadas = sign_request_headers(
            credentials=self._credentials,
            method=method,
            host=self._host,
            canonical_uri=self._ruta(key),
            headers=headers,
            now=self._clock(),
        )
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as cliente:
                return await cliente.request(
                    method,
                    f"https://{self._host}{self._ruta(key)}",
                    headers=firmadas,
                    content=content,
                )
        except httpx.HTTPError as exc:
            # Sin la URL ni las cabeceras: llevan la firma.
            raise AttachmentStorageError(
                f"R2 no respondió a {method}: {type(exc).__name__}"
            ) from exc

    async def head(self, key: str) -> StoredObjectInfo | None:
        respuesta = await self._pedir("HEAD", key, {"x-amz-checksum-mode": "ENABLED"})
        if respuesta.status_code == 404:
            return None
        if respuesta.status_code != 200:
            raise AttachmentStorageError(f"R2 respondió {respuesta.status_code} a HEAD")
        return StoredObjectInfo(
            size_bytes=int(respuesta.headers["content-length"]),
            sha256_hex=base64_a_sha256_hex(respuesta.headers.get("x-amz-checksum-sha256")),
        )

    async def get_bytes(self, key: str) -> bytes:
        respuesta = await self._pedir("GET", key)
        if respuesta.status_code != 200:
            raise AttachmentStorageError(f"R2 respondió {respuesta.status_code} a GET")
        return respuesta.content

    async def copy(self, *, source_key: str, destination_key: str) -> None:
        origen = f"/{self._bucket}/{uri_encode(source_key, encode_slash=False)}"
        respuesta = await self._pedir("PUT", destination_key, {"x-amz-copy-source": origen})
        # S3 puede responder 200 con un <Error> en el cuerpo si la copia falla a medias.
        if respuesta.status_code != 200 or b"<Error>" in respuesta.content:
            raise AttachmentStorageError(f"R2 no pudo copiar el objeto ({respuesta.status_code})")

    async def delete(self, key: str) -> None:
        respuesta = await self._pedir("DELETE", key)
        if respuesta.status_code not in (200, 204, 404):
            raise AttachmentStorageError(f"R2 respondió {respuesta.status_code} a DELETE")

    async def put_bytes(self, key: str, data: bytes) -> None:
        checksum = sha256_hex_a_base64(hashlib.sha256(data).hexdigest())
        headers = {
            "content-length": str(len(data)),
            "x-amz-checksum-sha256": checksum,
            "Content-Type": "application/octet-stream",
        }
        respuesta = await self._pedir("PUT", key, headers=headers, content=data)
        if respuesta.status_code not in (200, 201):
            raise AttachmentStorageError(f"R2 respondió {respuesta.status_code} a PUT")

