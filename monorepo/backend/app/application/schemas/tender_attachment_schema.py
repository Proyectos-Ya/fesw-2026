from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.domain.entities.attachment_file import (
    AttachmentFileSource,
    AttachmentFileStatus,
    AttachmentTrust,
    AttachmentVisibility,
)
from app.domain.entities.tender_attachment import AttachmentStatus
from app.domain.services.attachment_files import MAX_ATTACHMENT_SIZE_BYTES
from app.shared.datetime_utils import UtcDateTime


class AttachmentFileResponse(BaseModel):
    """Un archivo subido, tal como lo ve la empresa que consulta."""

    id: UUID
    size_bytes: int
    source: AttachmentFileSource
    visibility: AttachmentVisibility
    trust: AttachmentTrust
    status: AttachmentFileStatus
    is_mine: bool  # lo subió la empresa activa (y por eso puede borrarlo)
    created_at: UtcDateTime


class UploadQuotaResponse(BaseModel):
    """Subidas nuevas de la empresa este mes (hora de Chile) y su tope."""

    used: int
    limit: int


class OfficialAttachmentResponse(BaseModel):
    """Un anexo oficial y su estado en Chiripa."""

    id: UUID
    mp_document_id: int
    name: str
    # Forma canónica del nombre, calculada por el backend: el frontend la compara
    # con la del archivo que se suelta para saber a qué anexo corresponde.
    name_normalized: str
    ext: str  # minúsculas, sin punto; vacía si el nombre no trae una reconocible
    status: AttachmentStatus
    file: AttachmentFileResponse | None = None


class TenderAttachmentsResponse(BaseModel):
    """Lista oficial de anexos de una licitación."""

    official: list[OfficialAttachmentResponse]
    # Nulo = la lista todavía no se sincroniza, que no es lo mismo que "sin anexos".
    list_synced_at: UtcDateTime | None = None
    # Nulo sin empresa activa.
    quota: UploadQuotaResponse | None = None
    # El rol de la empresa activa puede subir y hay almacenamiento configurado.
    can_upload: bool = False
    max_upload_size_bytes: int = MAX_ATTACHMENT_SIZE_BYTES


class AttachmentUploadUrlRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    # Sin `le=MAX`: pasarse del máximo es un 413 del caso de uso, no un 422.
    size_bytes: int = Field(gt=0)
    mime: str = Field(default="", max_length=255)
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")

    @field_validator("sha256")
    @classmethod
    def _en_minusculas(cls, valor: str) -> str:
        return valor.lower()


class AttachmentUploadTicketResponse(BaseModel):
    """Hay que subir el archivo: PUT directo a `url` con exactamente estas cabeceras."""

    deduplicated: Literal[False] = False
    upload_id: UUID  # es el id del archivo: `complete` y el borrado usan el mismo
    url: str
    method: Literal["PUT"] = "PUT"
    headers: dict[str, str]
    expires_at: UtcDateTime


class AttachmentUploadDeduplicatedResponse(BaseModel):
    """Ya existe ese archivo para la empresa: no hay nada que subir."""

    deduplicated: Literal[True] = True
    file: AttachmentFileResponse


class AttachmentErrorResponse(BaseModel):
    """Cuerpo de los errores de la subida; `code` es estable y `detail` va en español."""

    detail: str
    code: str
    expected_name: str | None = None
    expected_ext: str | None = None
    received_ext: str | None = None
    used: int | None = None
    limit: int | None = None
    max_size_bytes: int | None = None
