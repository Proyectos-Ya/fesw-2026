"""Un archivo subido para un anexo oficial (plan 233, decisión 2).

Pertenece a una empresa (`workspace_id`), no a la persona que lo subió: si la
cuenta se borra, `uploader_user_id` queda nulo y el archivo sigue. `visibility`
y `trust` nacen en `private` y `pending`; los cambia la decisión 6.
"""

from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel

# Una subida que no se confirma en un día se puede limpiar (decisión futura).
PLAZO_DE_SUBIDA_INCOMPLETA = timedelta(hours=24)


class AttachmentFileStatus(StrEnum):
    UPLOADING = "uploading"
    STORED = "stored"
    UNSUPPORTED = "unsupported"
    REJECTED = "rejected"
    PURGED = "purged"


class AttachmentFileSource(StrEnum):
    MANUAL = "manual"
    EXTENSION = "extension"  # decisión 7
    LEGACY_CHAT = "legacy_chat"  # migración de los documentos del chat


class AttachmentVisibility(StrEnum):
    PRIVATE = "private"
    SHARED = "shared"


class AttachmentTrust(StrEnum):
    PENDING = "pending"
    CORROBORATED = "corroborated"
    CONFLICT = "conflict"
    REJECTED = "rejected"


class AttachmentFile(BaseModel):
    id: UUID
    tender_attachment_id: UUID
    tender_id: UUID
    sha256: str  # hex en minúsculas, 64 caracteres
    size_bytes: int
    mime_declared: str | None = None
    storage_key: str
    source: AttachmentFileSource
    uploader_user_id: UUID | None
    workspace_id: UUID
    visibility: AttachmentVisibility = AttachmentVisibility.PRIVATE
    trust: AttachmentTrust = AttachmentTrust.PENDING
    status: AttachmentFileStatus
    created_at: datetime
    completed_at: datetime | None = None
    purge_after: datetime | None = None

    def visible_para(self, workspace_id: UUID | None) -> bool:
        """Un archivo compartido lo ve cualquiera; uno privado, solo su empresa."""
        if self.visibility == AttachmentVisibility.SHARED:
            return True
        return workspace_id is not None and self.workspace_id == workspace_id

    def como_subiendo(
        self,
        *,
        size_bytes: int,
        mime_declared: str | None,
        uploader_user_id: UUID,
        ahora: datetime,
    ) -> "AttachmentFile":
        """Reintento de una fila `uploading`, `rejected` o `purged`: vuelve a empezar."""
        return self.model_copy(
            update={
                "status": AttachmentFileStatus.UPLOADING,
                "size_bytes": size_bytes,
                "mime_declared": mime_declared,
                "uploader_user_id": uploader_user_id,
                "completed_at": None,
                "purge_after": ahora + PLAZO_DE_SUBIDA_INCOMPLETA,
            }
        )

    def como_guardado(self, *, ahora: datetime) -> "AttachmentFile":
        """El objeto llegó y se verificó: ya no hay nada que limpiar."""
        return self.model_copy(
            update={
                "status": AttachmentFileStatus.STORED,
                "completed_at": ahora,
                "purge_after": None,
            }
        )

    def como_rechazado(self, *, ahora: datetime) -> "AttachmentFile":
        """El objeto no coincide con lo declarado: queda para limpiar de inmediato."""
        return self.model_copy(
            update={
                "status": AttachmentFileStatus.REJECTED,
                "completed_at": ahora,
                "purge_after": ahora,
            }
        )
