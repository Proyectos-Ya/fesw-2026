"""Dobles en memoria para la subida manual de anexos (plan 233, decisión 2).

Van aparte de `fakes.py` (mismo patrón que `attachment_fakes.py`): ese archivo
diverge mucho respecto de `develop` y cada cambio ahí es un conflicto de merge.
"""

import hashlib
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from app.application.repositories.attachment_file_repository import (
    IAttachmentFileRepository,
)
from app.application.services.attachment_storage import (
    IAttachmentStorage,
    PresignedUpload,
    StoredObjectInfo,
)
from app.application.services.attachment_stored_listener import (
    IAttachmentStoredListener,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileStatus,
    AttachmentVisibility,
)
from app.domain.errors.attachment_errors import (
    AttachmentFileNotFound,
    ConcurrentUploadConflict,
    UploadQuotaExceeded,
)
from app.domain.services.attachment_files import tiene_archivo


class InMemoryAttachmentFileRepository(IAttachmentFileRepository):
    """Mismas reglas que el repositorio SQL, incluida la clave única y el cupo atómico."""

    def __init__(self) -> None:
        self.filas: dict[UUID, AttachmentFile] = {}
        self.cupo: dict[tuple[UUID, date], int] = {}

    async def get(self, file_id: UUID) -> AttachmentFile | None:
        return self.filas.get(file_id)

    async def find_for_workspace(
        self, *, tender_attachment_id: UUID, sha256: str, workspace_id: UUID
    ) -> AttachmentFile | None:
        for fila in self.filas.values():
            if (
                fila.tender_attachment_id == tender_attachment_id
                and fila.sha256 == sha256
                and fila.workspace_id == workspace_id
            ):
                return fila
        return None

    async def find_shared_stored(
        self, *, tender_attachment_id: UUID, sha256: str
    ) -> AttachmentFile | None:
        for fila in self.filas.values():
            if (
                fila.tender_attachment_id == tender_attachment_id
                and fila.sha256 == sha256
                and fila.visibility == AttachmentVisibility.SHARED
                and fila.status == AttachmentFileStatus.STORED
            ):
                return fila
        return None

    async def find_stored_by_storage_key(self, storage_key: str) -> AttachmentFile | None:
        for fila in self.filas.values():
            if fila.storage_key == storage_key and tiene_archivo(fila):
                return fila
        return None

    async def list_for_workspace_attachment(
        self, *, tender_attachment_id: UUID, workspace_id: UUID
    ) -> list[AttachmentFile]:
        return [
            f
            for f in self.filas.values()
            if f.tender_attachment_id == tender_attachment_id
            and f.workspace_id == workspace_id
        ]

    async def list_visible_for_tender(
        self, *, tender_id: UUID, workspace_id: UUID | None
    ) -> list[AttachmentFile]:
        return [
            f
            for f in self.filas.values()
            if f.tender_id == tender_id
            and f.status != AttachmentFileStatus.PURGED
            and f.visible_para(workspace_id)
        ]

    def _chocan(self, file: AttachmentFile) -> bool:
        return any(
            f.tender_attachment_id == file.tender_attachment_id
            and f.sha256 == file.sha256
            and f.workspace_id == file.workspace_id
            for f in self.filas.values()
        )

    async def create(self, file: AttachmentFile) -> AttachmentFile:
        if self._chocan(file):
            raise ConcurrentUploadConflict()
        self.filas[file.id] = file
        return file

    async def create_consuming_quota(
        self, file: AttachmentFile, *, month: date, limit: int
    ) -> AttachmentFile:
        clave = (file.workspace_id, month)
        usado = self.cupo.get(clave, 0)
        # Primero el cupo, después la clave única, y recién entonces se suma: así un
        # choque no cobra, igual que el rollback de la transacción SQL.
        if usado >= limit:
            raise UploadQuotaExceeded(used=usado, limit=limit)
        if self._chocan(file):
            raise ConcurrentUploadConflict()
        self.cupo[clave] = usado + 1
        self.filas[file.id] = file
        return file

    async def update(self, file: AttachmentFile) -> AttachmentFile:
        if file.id not in self.filas:
            raise AttachmentFileNotFound()
        self.filas[file.id] = file
        return file

    async def delete(self, file_id: UUID) -> None:
        self.filas.pop(file_id, None)

    async def count_other_references(self, *, storage_key: str, excluding_id: UUID) -> int:
        return sum(
            1
            for f in self.filas.values()
            if f.storage_key == storage_key
            and f.id != excluding_id
            and f.status != AttachmentFileStatus.PURGED
        )

    async def get_quota_used(self, *, workspace_id: UUID, month: date) -> int:
        return self.cupo.get((workspace_id, month), 0)


class FakeAttachmentStorage(IAttachmentStorage):
    """Almacenamiento en memoria. `subir` simula el PUT del navegador."""

    def __init__(self, informa_checksum: bool = True) -> None:
        self.informa_checksum = informa_checksum
        self.objetos: dict[str, bytes] = {}
        self.firmadas: list[dict[str, Any]] = []
        self.borradas: list[str] = []
        self.copias: list[tuple[str, str]] = []
        self.heads = 0
        self.falla_con: Exception | None = None

    def _fallar(self) -> None:
        if self.falla_con is not None:
            raise self.falla_con

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
        self._fallar()
        self.firmadas.append(
            {
                "key": key,
                "size_bytes": size_bytes,
                "sha256_hex": sha256_hex,
                "content_type": content_type,
                "expires_in_seconds": expires_in_seconds,
                "now": now,
            }
        )
        return PresignedUpload(
            url=f"https://almacen.test/{key}?firma=x",
            method="PUT",
            headers={"x-amz-checksum-sha256": "b64", "Content-Type": content_type},
            expires_at=now + timedelta(seconds=expires_in_seconds),
        )

    def subir(self, key: str, data: bytes) -> None:
        self.objetos[key] = data

    async def head(self, key: str) -> StoredObjectInfo | None:
        self.heads += 1
        self._fallar()
        data = self.objetos.get(key)
        if data is None:
            return None
        sha = hashlib.sha256(data).hexdigest() if self.informa_checksum else None
        return StoredObjectInfo(len(data), sha)

    async def get_bytes(self, key: str) -> bytes:
        self._fallar()
        return self.objetos[key]

    async def copy(self, *, source_key: str, destination_key: str) -> None:
        self._fallar()
        self.copias.append((source_key, destination_key))
        self.objetos[destination_key] = self.objetos[source_key]

    async def delete(self, key: str) -> None:
        self._fallar()
        self.borradas.append(key)
        self.objetos.pop(key, None)


class RecordingStoredListener(IAttachmentStoredListener):
    def __init__(self, falla_con: Exception | None = None) -> None:
        self.recibidos: list[AttachmentFile] = []
        self.falla_con = falla_con

    async def on_stored(self, file: AttachmentFile) -> None:
        self.recibidos.append(file)
        if self.falla_con is not None:
            raise self.falla_con
