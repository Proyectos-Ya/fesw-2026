from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.application.repositories.tender_attachment_repository import (
    ITenderAttachmentRepository,
)
from app.domain.entities.tender_attachment import AttachmentStatus, OfficialAttachment
from app.domain.errors.tender_errors import TenderNotFound


@dataclass(frozen=True)
class OfficialAttachmentView:
    attachment: OfficialAttachment
    status: AttachmentStatus


@dataclass(frozen=True)
class TenderAttachmentsResult:
    official: list[OfficialAttachmentView]
    # None = la lista todavía no se sincroniza; no es lo mismo que "sin anexos".
    list_synced_at: datetime | None


class GetTenderAttachmentsUseCase:
    """La lista oficial de anexos de una licitación, con su estado en Chiripa."""

    def __init__(self, attachments: ITenderAttachmentRepository) -> None:
        self.attachments = attachments

    async def execute(self, tender_id: UUID) -> TenderAttachmentsResult:
        lista = await self.attachments.get_official_list(tender_id)
        if lista is None:
            raise TenderNotFound(tender_id)
        # Hoy todo anexo "falta": la subida (decisión 2) calculará el estado real acá.
        return TenderAttachmentsResult(
            official=[
                OfficialAttachmentView(a, AttachmentStatus.MISSING)
                for a in lista.attachments
            ],
            list_synced_at=lista.synced_at,
        )
