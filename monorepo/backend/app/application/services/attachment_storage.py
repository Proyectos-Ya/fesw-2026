"""Puerto del almacenamiento de objetos de los anexos (plan 233, decisión 2).

Lo implementan Cloudflare R2 (producción) y el disco local (desarrollo). Las
claves son rutas con `/` (`private/{empresa}/{sha256}.{ext}`); el adaptador
decide cómo llevarlas al medio.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class PresignedUpload:
    url: str
    method: Literal["PUT"]
    headers: dict[str, str]
    expires_at: datetime  # UTC naive


@dataclass(frozen=True)
class StoredObjectInfo:
    size_bytes: int
    # None = el almacenamiento no informa el checksum (R2 podría no hacerlo).
    sha256_hex: str | None


class AttachmentStorageError(Exception):
    """El almacenamiento falló o no respondió. El router lo traduce a 502 `storage_error`."""


class IAttachmentStorage(ABC):
    @abstractmethod
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
        """URL para que el navegador suba el archivo directo, atada a su tamaño y huella."""
        ...

    @abstractmethod
    async def head(self, key: str) -> StoredObjectInfo | None:
        """Tamaño y checksum del objeto; `None` si no existe."""
        ...

    @abstractmethod
    async def get_bytes(self, key: str) -> bytes:
        """El contenido completo (decisión 4: extracción de texto)."""
        ...

    @abstractmethod
    async def copy(self, *, source_key: str, destination_key: str) -> None:
        """Copia un objeto (decisión 6: promover a `shared/`)."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Borra el objeto. Idempotente: que no exista no es un error."""
        ...
