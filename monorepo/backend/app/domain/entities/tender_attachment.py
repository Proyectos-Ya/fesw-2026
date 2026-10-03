from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class AttachmentStatus(StrEnum):
    """Estado de un anexo oficial para quien mira la ficha.

    Hoy solo `missing`: Chiripa conoce la lista, no los archivos. La subida
    (plan 233, decisión 2) agrega los demás.
    """

    MISSING = "missing"


class OfficialAttachment(BaseModel):
    """Un anexo que Mercado Público publica para una licitación."""

    id: UUID
    tender_id: UUID
    mp_document_id: int
    name: str
    name_normalized: str
    ext: str
    first_seen_at: datetime
    last_seen_at: datetime
    removed_at: datetime | None = None


class OfficialAttachmentList(BaseModel):
    """La lista vigente (sin retirados, por `mp_document_id`) y cuándo se vio por última vez."""

    attachments: list[OfficialAttachment]
    synced_at: datetime | None = None  # None = nunca se sincronizó
