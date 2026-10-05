"""Dobles en memoria para la subida manual de anexos (plan 233, decisión 2).

Van aparte de `fakes.py` (mismo patrón que `attachment_fakes.py`): ese archivo
diverge mucho respecto de `develop` y cada cambio ahí es un conflicto de merge.
"""

import hashlib
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from app.application.repositories.attachment_file_repository import (
    IAttachmentFileRepository,
)
from app.application.repositories.attachment_trust_repository import (
    IAttachmentTrustRepository,
    TrustSnapshot,
)
from app.application.services.attachment_deleted_listener import (
    IAttachmentDeletedListener,
)
from app.application.services.attachment_storage import (
    IAttachmentStorage,
    PresignedUpload,
    StoredObjectInfo,
)
from app.application.services.attachment_stored_listener import (
    IAttachmentStoredListener,
)
from app.application.services.attachment_visibility_listener import (
    IAttachmentVisibilityListener,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
    AttachmentTrust,
    AttachmentVisibility,
)
from app.domain.errors.attachment_errors import (
    AttachmentFileNotFound,
    ConcurrentUploadConflict,
    UploadQuotaExceeded,
)
from app.domain.services.attachment_files import tiene_archivo
from tests.unit.application.attachment_fakes import InMemoryTenderAttachmentRepository


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
        self.get_bytes_count = 0
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

    async def put_bytes(self, key: str, data: bytes) -> None:
        self._fallar()
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
        self.get_bytes_count += 1
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


class RecordingDeletedListener(IAttachmentDeletedListener):
    def __init__(self, falla_con: Exception | None = None) -> None:
        self.recibidos: list[AttachmentFile] = []
        self.falla_con = falla_con

    async def on_deleted(self, file: AttachmentFile) -> None:
        self.recibidos.append(file)
        if self.falla_con is not None:
            raise self.falla_con


class RecordingVisibilityListener(IAttachmentVisibilityListener):
    def __init__(self, falla_con: Exception | None = None) -> None:
        self.recibidos: list[AttachmentFile] = []
        self.falla_con = falla_con

    async def on_visibility_changed(self, file: AttachmentFile) -> None:
        self.recibidos.append(file)
        if self.falla_con is not None:
            raise self.falla_con


def canonico(
    *,
    tender_attachment_id: UUID,
    tender_id: UUID,
    sha256: str,
    storage_key: str | None = None,
    size_bytes: int = 4,
    visibility: AttachmentVisibility = AttachmentVisibility.SHARED,
    trust: AttachmentTrust = AttachmentTrust.CORROBORATED,
    source: AttachmentFileSource = AttachmentFileSource.MANUAL,
    created_at: datetime = datetime(2026, 10, 3, 15, 0),
) -> AttachmentFile:
    """Una versión canónica válida (sin empresa ni autor), como la deja la promoción."""
    return AttachmentFile(
        id=uuid4(),
        tender_attachment_id=tender_attachment_id,
        tender_id=tender_id,
        sha256=sha256,
        size_bytes=size_bytes,
        storage_key=storage_key or f"shared/{tender_id}/1931002/{sha256}.xlsx",
        source=source,
        uploader_user_id=None,
        workspace_id=None,
        visibility=visibility,
        trust=trust,
        status=AttachmentFileStatus.STORED,
        created_at=created_at,
        completed_at=created_at,
    )


class InMemoryAttachmentTrustRepository(IAttachmentTrustRepository):
    """Mismo contrato que el SQL, sin candado real. Cuenta aperturas y cierres.

    Invariante que los tests verifican: toda `lock_for_promotion` termina en un
    `save_promotion` o en un `release` (`abiertas == liberadas + guardadas`).
    """

    def __init__(
        self,
        *,
        files: InMemoryAttachmentFileRepository,
        attachments: InMemoryTenderAttachmentRepository,
        personas: Mapping[UUID, frozenset[UUID]] | None = None,
    ) -> None:
        self.files = files
        self.attachments = attachments
        self.personas = dict(personas or {})
        self.abiertas = 0
        self.liberadas = 0
        self.guardadas = 0

    async def lock_for_promotion(self, tender_attachment_id: UUID) -> TrustSnapshot | None:
        self.abiertas += 1
        anexo = next(
            (a for a in self.attachments.filas.values() if a.id == tender_attachment_id),
            None,
        )
        if anexo is None:
            return None
        archivos = [
            f
            for f in self.files.filas.values()
            if f.tender_attachment_id == tender_attachment_id
            and f.status != AttachmentFileStatus.PURGED
        ]
        empresas = {f.workspace_id for f in archivos if f.workspace_id is not None}
        return TrustSnapshot(
            attachment=anexo,
            files=archivos,
            people={e: self.personas.get(e, frozenset()) for e in empresas},
        )

    async def save_promotion(
        self, *, updated: Sequence[AttachmentFile], created: Sequence[AttachmentFile]
    ) -> None:
        # Se arma el resultado aparte y recién al final se aplica: si un índice lo
        # rechaza, no queda nada a medias, igual que el rollback de SQL.
        resultado = dict(self.files.filas)
        for nuevo in updated:
            actual = resultado[nuevo.id]
            resultado[nuevo.id] = actual.model_copy(
                update={"trust": nuevo.trust, "visibility": nuevo.visibility}
            )
        for fila in created:
            # Emula el único parcial `(anexo, sha) WHERE workspace_id IS NULL`.
            if any(
                f.tender_attachment_id == fila.tender_attachment_id
                and f.sha256 == fila.sha256
                and f.workspace_id == fila.workspace_id
                for f in resultado.values()
            ):
                raise ConcurrentUploadConflict()
            resultado[fila.id] = fila
        # Emula el único parcial `(anexo) WHERE visibility = 'shared'`.
        compartidas: set[UUID] = set()
        for f in resultado.values():
            if f.visibility == AttachmentVisibility.SHARED:
                assert f.tender_attachment_id not in compartidas, "dos versiones compartidas"
                compartidas.add(f.tender_attachment_id)
        self.files.filas.clear()
        self.files.filas.update(resultado)
        self.guardadas += 1

    async def release(self) -> None:
        self.liberadas += 1
