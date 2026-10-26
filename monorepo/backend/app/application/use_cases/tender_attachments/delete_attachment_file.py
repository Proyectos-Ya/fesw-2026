"""Borrar un archivo de anexo de la empresa (plan 233, decisiones 2 y 6)."""

import logging
from uuid import UUID

from app.application.repositories.attachment_file_repository import (
    IAttachmentFileRepository,
)
from app.application.services.attachment_deleted_listener import (
    IAttachmentDeletedListener,
    NoopAttachmentDeletedListener,
)
from app.application.services.attachment_storage import IAttachmentStorage
from app.domain.entities.attachment_file import AttachmentVisibility
from app.domain.errors.attachment_errors import (
    AttachmentFileIsShared,
    AttachmentFileNotFound,
    AttachmentStorageUnavailable,
    NotAttachmentFileOwner,
)
from app.domain.services.attachment_trust import visibilidad_efectiva

logger = logging.getLogger(__name__)


class DeleteAttachmentFileUseCase:
    """Borra la fila y, si nadie más lo usa, el objeto. El cupo no se devuelve.

    No borra lo que ya se comparte, tampoco el aporte propio ya corroborado (su
    contenido lo ven todas por la copia canónica y borrarlo no "descomparte" nada).
    Después de borrar avisa a la promoción, que reevalúa el anexo.
    """

    def __init__(
        self,
        *,
        files: IAttachmentFileRepository,
        storage: IAttachmentStorage | None,
        listener: IAttachmentDeletedListener | None = None,
    ) -> None:
        self.files = files
        self.storage = storage
        self.listener = listener or NoopAttachmentDeletedListener()

    async def execute(self, *, tender_id: UUID, file_id: UUID, workspace_id: UUID) -> None:
        if self.storage is None:
            raise AttachmentStorageUnavailable()

        archivo = await self.files.get(file_id)
        # El privado de otra empresa responde igual que un id inexistente, y también
        # la versión canónica que un conflicto ocultó (no es visible para nadie).
        if (
            archivo is None
            or archivo.tender_id != tender_id
            or not archivo.visible_para(workspace_id)
        ):
            raise AttachmentFileNotFound()
        # La canónica visible no es de ninguna empresa: `None != workspace_id`.
        if archivo.workspace_id != workspace_id:
            raise NotAttachmentFileOwner()
        if visibilidad_efectiva(archivo) == AttachmentVisibility.SHARED:
            raise AttachmentFileIsShared()

        # Dos anexos de la empresa con el mismo contenido comparten el objeto
        # (deduplicación por clave): borrar uno no puede romper el otro.
        otras = await self.files.count_other_references(
            storage_key=archivo.storage_key, excluding_id=archivo.id
        )
        if otras == 0:
            # Primero el objeto: si falla, la fila sigue y se puede reintentar. Al
            # revés quedaría un archivo huérfano que nadie ve ni puede borrar.
            await self.storage.delete(archivo.storage_key)
        await self.files.delete(archivo.id)
        # Decisión 6: borrar una versión que chocaba puede destrabar lo compartido.
        # Un fallo solo se registra: el borrado ya ocurrió.
        try:
            await self.listener.on_deleted(archivo)
        except Exception:
            logger.exception("El listener de archivos borrados falló (archivo %s).", archivo.id)
