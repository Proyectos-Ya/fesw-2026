"""Borrar un archivo de anexo de la empresa (plan 233, decisión 2)."""

from uuid import UUID

from app.application.repositories.attachment_file_repository import (
    IAttachmentFileRepository,
)
from app.application.services.attachment_storage import IAttachmentStorage
from app.domain.entities.attachment_file import AttachmentVisibility
from app.domain.errors.attachment_errors import (
    AttachmentFileIsShared,
    AttachmentFileNotFound,
    AttachmentStorageUnavailable,
    NotAttachmentFileOwner,
)


class DeleteAttachmentFileUseCase:
    """Borra la fila y, si nadie más lo usa, el objeto. El cupo no se devuelve."""

    def __init__(
        self, *, files: IAttachmentFileRepository, storage: IAttachmentStorage | None
    ) -> None:
        self.files = files
        self.storage = storage

    async def execute(self, *, tender_id: UUID, file_id: UUID, workspace_id: UUID) -> None:
        if self.storage is None:
            raise AttachmentStorageUnavailable()

        archivo = await self.files.get(file_id)
        # El privado de otra empresa responde igual que un id inexistente.
        if (
            archivo is None
            or archivo.tender_id != tender_id
            or not archivo.visible_para(workspace_id)
        ):
            raise AttachmentFileNotFound()
        if archivo.workspace_id != workspace_id:
            raise NotAttachmentFileOwner()
        if archivo.visibility == AttachmentVisibility.SHARED:
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
