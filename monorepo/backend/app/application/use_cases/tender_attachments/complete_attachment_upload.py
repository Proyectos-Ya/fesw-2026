"""Confirmar una subida (plan 233, decisión 2).

Tercer paso: el navegador avisa que terminó el PUT. Como los bytes no pasaron por
el backend, se comprueba con un HEAD que el objeto llegó y que es el declarado.
"""

import logging
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from app.application.repositories.attachment_file_repository import (
    IAttachmentFileRepository,
)
from app.application.services.attachment_storage import IAttachmentStorage
from app.application.services.attachment_stored_listener import (
    IAttachmentStoredListener,
)
from app.domain.entities.attachment_file import AttachmentFile, AttachmentFileStatus
from app.domain.errors.attachment_errors import (
    AttachmentStorageUnavailable,
    UploadedObjectMissing,
    UploadNotFound,
    UploadNotInProgress,
    UploadVerificationFailed,
)
from app.domain.services.attachment_files import tiene_archivo
from app.shared.datetime_utils import utc_now_naive

logger = logging.getLogger(__name__)


class CompleteAttachmentUploadUseCase:
    def __init__(
        self,
        *,
        files: IAttachmentFileRepository,
        storage: IAttachmentStorage | None,
        listener: IAttachmentStoredListener,
        clock: Callable[[], datetime] = utc_now_naive,
    ) -> None:
        self.files = files
        self.storage = storage
        self.listener = listener
        self.clock = clock

    async def execute(
        self, *, tender_id: UUID, upload_id: UUID, workspace_id: UUID
    ) -> AttachmentFile:
        if self.storage is None:
            raise AttachmentStorageUnavailable()

        archivo = await self.files.get(upload_id)
        # Una subida ajena responde igual que una inexistente: no revela que existe.
        if (
            archivo is None
            or archivo.tender_id != tender_id
            or archivo.workspace_id != workspace_id
        ):
            raise UploadNotFound()

        # Idempotente: confirmar dos veces no vuelve a verificar ni a avisar.
        if tiene_archivo(archivo):
            return archivo
        if archivo.status != AttachmentFileStatus.UPLOADING:
            raise UploadNotInProgress()

        info = await self.storage.head(archivo.storage_key)
        if info is None:
            raise UploadedObjectMissing()

        # El tamaño se verifica siempre; la huella, cuando el almacenamiento la
        # informa (R2 podría no hacerlo: la decisión 4 la recalcula al leer).
        coincide = info.size_bytes == archivo.size_bytes and (
            info.sha256_hex is None or info.sha256_hex == archivo.sha256
        )
        ahora = self.clock()
        if not coincide:
            # Solo se borra el objeto si ninguna otra fila lo usa: dos anexos de la
            # misma empresa con el mismo contenido comparten la clave.
            otras = await self.files.count_other_references(
                storage_key=archivo.storage_key, excluding_id=archivo.id
            )
            if otras == 0:
                await self.storage.delete(archivo.storage_key)
            rechazado = await self.files.update(archivo.como_rechazado(ahora=ahora))
            raise UploadVerificationFailed(rechazado)

        guardado = await self.files.update(archivo.como_guardado(ahora=ahora))
        # Decisión 4: acá se encola la extracción de texto, vía el listener.
        try:
            await self.listener.on_stored(guardado)
        except Exception:
            logger.exception("El listener de archivos guardados falló (archivo %s).", guardado.id)
        return guardado
