from uuid import UUID

from pydantic import BaseModel

from app.domain.entities.tender_attachment import AttachmentStatus
from app.shared.datetime_utils import UtcDateTime


class OfficialAttachmentResponse(BaseModel):
    """Un anexo oficial y su estado en Chiripa."""

    id: UUID
    mp_document_id: int
    name: str
    ext: str  # minúsculas, sin punto; vacía si el nombre no trae una reconocible
    status: AttachmentStatus


class TenderAttachmentsResponse(BaseModel):
    """Lista oficial de anexos de una licitación."""

    official: list[OfficialAttachmentResponse]
    # Nulo = la lista todavía no se sincroniza, que no es lo mismo que "sin anexos".
    list_synced_at: UtcDateTime | None = None
