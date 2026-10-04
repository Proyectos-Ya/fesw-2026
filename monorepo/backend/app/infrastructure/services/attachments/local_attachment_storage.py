"""Almacenamiento de anexos en disco local, SOLO para desarrollo (plan 233, decisión 2).

Imita a R2 lo justo para probar el flujo completo sin credenciales: la URL de
subida lleva un token HMAC (secreto aleatorio por proceso) que ata la clave, el
tamaño y la huella, y `escribir` verifica ambos mientras recibe el cuerpo.

La URL es **absoluta al backend**, no `/api`: el rewrite de Next corta los
cuerpos a 10 MB. Se monta solo sin R2 y con `IS_DEV` (ver `bootstrap`).
"""

import asyncio
import hashlib
import hmac
import os
import shutil
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urlencode
from uuid import uuid4

from app.application.services.attachment_storage import (
    AttachmentStorageError,
    IAttachmentStorage,
    PresignedUpload,
    StoredObjectInfo,
)
from app.infrastructure.services.attachments.checksums import sha256_hex_a_base64
from app.shared.datetime_utils import to_utc_epoch


class ContenidoInvalido(ValueError):
    """Lo recibido no tiene el tamaño o la huella que firmó la URL."""


class LocalDiskAttachmentStorage(IAttachmentStorage):
    def __init__(self, *, root: Path, public_base_url: str, secret: bytes) -> None:
        # No crea directorios acá: se construye al importar `app.main` en los tests.
        self._root = root
        self._base = public_base_url.rstrip("/")
        self._secret = secret

    def ruta_de(self, key: str) -> Path:
        """El archivo de esa clave; rechaza cualquier cosa que se salga de la raíz."""
        segmentos = key.split("/")
        if not key or "\\" in key or any(s in ("", ".", "..") for s in segmentos):
            raise ValueError(f"Clave de almacenamiento inválida: {key!r}")
        ruta = self._root.joinpath(*segmentos)
        if not ruta.resolve().is_relative_to(self._root.resolve()):
            raise ValueError(f"Clave de almacenamiento inválida: {key!r}")
        return ruta

    def _firma(self, key: str, expires: int, size: int, sha256_hex: str) -> str:
        mensaje = f"PUT\n{key}\n{expires}\n{size}\n{sha256_hex}".encode()
        return hmac.new(self._secret, mensaje, hashlib.sha256).hexdigest()

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
        self.ruta_de(key)  # falla temprano con una clave inválida
        expires_at = now + timedelta(seconds=expires_in_seconds)
        expires = to_utc_epoch(expires_at)
        consulta = urlencode(
            {
                "expires": expires,
                "size": size_bytes,
                "sha256": sha256_hex,
                "token": self._firma(key, expires, size_bytes, sha256_hex),
            }
        )
        return PresignedUpload(
            url=f"{self._base}/dev-storage/{quote(key, safe='/')}?{consulta}",
            method="PUT",
            # Los mismos headers que en R2: el cliente no distingue el adaptador.
            headers={
                "x-amz-checksum-sha256": sha256_hex_a_base64(sha256_hex),
                "Content-Type": content_type,
            },
            expires_at=expires_at,
        )

    def verificar_token(
        self,
        *,
        key: str,
        expires: int,
        size: int,
        sha256_hex: str,
        token: str,
        now: datetime,
    ) -> bool:
        esperado = self._firma(key, expires, size, sha256_hex)
        return to_utc_epoch(now) <= expires and hmac.compare_digest(esperado, token)

    async def escribir(
        self, key: str, partes: AsyncIterator[bytes], *, size: int, sha256_hex: str
    ) -> None:
        """Guarda el cuerpo si tiene exactamente `size` bytes y esa huella.

        Escribe a un `.part` en el mismo directorio y lo renombra al final, así
        nadie lee un archivo a medias ni queda uno inválido si algo falla.
        """
        destino = self.ruta_de(key)
        await asyncio.to_thread(destino.parent.mkdir, parents=True, exist_ok=True)
        temporal = destino.with_name(f"{destino.name}.{uuid4().hex}.part")
        digest = hashlib.sha256()
        recibidos = 0
        try:
            with temporal.open("wb") as salida:
                async for parte in partes:
                    recibidos += len(parte)
                    if recibidos > size:
                        raise ContenidoInvalido("El cuerpo supera el tamaño declarado.")
                    digest.update(parte)
                    await asyncio.to_thread(salida.write, parte)
            if recibidos != size or digest.hexdigest() != sha256_hex:
                raise ContenidoInvalido("El cuerpo no coincide con el tamaño o la huella.")
            await asyncio.to_thread(os.replace, temporal, destino)
        finally:
            await asyncio.to_thread(temporal.unlink, missing_ok=True)

    async def head(self, key: str) -> StoredObjectInfo | None:
        ruta = self.ruta_de(key)
        return await asyncio.to_thread(self._leer_info, ruta)

    @staticmethod
    def _leer_info(ruta: Path) -> StoredObjectInfo | None:
        if not ruta.is_file():
            return None
        digest = hashlib.sha256()
        with ruta.open("rb") as entrada:
            for bloque in iter(lambda: entrada.read(1024 * 1024), b""):
                digest.update(bloque)
        return StoredObjectInfo(ruta.stat().st_size, digest.hexdigest())

    async def get_bytes(self, key: str) -> bytes:
        ruta = self.ruta_de(key)
        try:
            return await asyncio.to_thread(ruta.read_bytes)
        except OSError as exc:
            raise AttachmentStorageError("El objeto no existe en el disco local.") from exc

    async def copy(self, *, source_key: str, destination_key: str) -> None:
        origen, destino = self.ruta_de(source_key), self.ruta_de(destination_key)

        def _copiar() -> None:
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origen, destino)

        try:
            await asyncio.to_thread(_copiar)
        except OSError as exc:
            raise AttachmentStorageError("El objeto de origen no existe.") from exc

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.ruta_de(key).unlink, missing_ok=True)
