"""Caso de uso: Comprobación de estado de anexos desde la extensión."""

from uuid import UUID

from app.application.repositories.attachment_file_repository import (
    IAttachmentFileRepository,
)
from app.application.repositories.tender_attachment_repository import (
    ITenderAttachmentRepository,
)
from app.application.schemas.extension_schema import (
    DocumentCheckStatus,
    ExtensionAttachmentCheckRequest,
    ExtensionAttachmentCheckResponse,
)
from app.domain.entities.attachment_file import AttachmentFileStatus


class CheckExtensionAttachmentsUseCase:
    """Verifica cuáles documentos de una licitación ya han sido descargados e indexados."""

    def __init__(
        self,
        tender_attachment_repo: ITenderAttachmentRepository,
        attachment_file_repo: IAttachmentFileRepository,
    ) -> None:
        self.tender_attachment_repo = tender_attachment_repo
        self.attachment_file_repo = attachment_file_repo

    async def execute(
        self, request: ExtensionAttachmentCheckRequest
    ) -> ExtensionAttachmentCheckResponse:
        code_map = await self.tender_attachment_repo.get_tender_ids_by_codes(
            [request.tender_code]
        )
        tender_id = code_map.get(request.tender_code)

        if not tender_id:
            return ExtensionAttachmentCheckResponse(
                tender_id=None,
                tender_code=request.tender_code,
                documents=[
                    DocumentCheckStatus(
                        mp_document_id=doc.mp_document_id,
                        name=doc.name,
                        attachment_id=None,
                        status="missing",
                        exists=False,
                    )
                    for doc in request.documents
                ],
            )

        official_list = await self.tender_attachment_repo.get_official_list(tender_id)
        attachments_by_mp_id = {}
        if official_list:
            for att in official_list.attachments:
                attachments_by_mp_id[str(att.mp_document_id)] = att

        statuses: list[DocumentCheckStatus] = []
        for doc in request.documents:
            att = attachments_by_mp_id.get(doc.mp_document_id)
            if not att:
                statuses.append(
                    DocumentCheckStatus(
                        mp_document_id=doc.mp_document_id,
                        name=doc.name,
                        attachment_id=None,
                        status="missing",
                        exists=False,
                    )
                )
                continue

            canonical_file = await self.attachment_file_repo.get_canonical_file(
                tender_id, att.id
            )
            is_stored = bool(
                canonical_file and canonical_file.status == AttachmentFileStatus.STORED
            )

            statuses.append(
                DocumentCheckStatus(
                    mp_document_id=doc.mp_document_id,
                    name=doc.name,
                    attachment_id=att.id,
                    status="stored" if is_stored else "missing",
                    exists=is_stored,
                )
            )

        return ExtensionAttachmentCheckResponse(
            tender_id=tender_id,
            tender_code=request.tender_code,
            documents=statuses,
        )
