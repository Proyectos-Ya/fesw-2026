from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.application.repositories.attachment_file_repository import (
    IAttachmentFileRepository,
)
from app.application.repositories.attachment_processing_status_reader import (
    IAttachmentProcessingStatusReader,
)
from app.application.repositories.tender_attachment_repository import (
    ITenderAttachmentRepository,
)
from app.domain.entities.attachment_extraction import EXTRACTION_PROMPT_VERSION
from app.domain.entities.attachment_file import AttachmentFile
from app.domain.entities.attachment_processing import (
    EstadoDeExtraccion,
    ProcessingState,
    estado_de_procesamiento,
)
from app.domain.entities.tender_attachment import AttachmentStatus, OfficialAttachment
from app.domain.errors.tender_errors import TenderNotFound
from app.domain.services.attachment_files import (
    MAX_ATTACHMENT_SIZE_BYTES,
    elegir_archivo_visible,
    estado_del_anexo,
    mes_de_cuota,
)
from app.domain.services.attachment_trust import es_propio
from app.shared.datetime_utils import utc_now_naive


@dataclass(frozen=True)
class WorkspaceAccess:
    """Quién mira la ficha: la empresa activa y si su rol puede subir anexos."""

    workspace_id: UUID
    can_upload: bool  # el rol tiene `upload_attachments`


@dataclass(frozen=True)
class UploadQuota:
    used: int
    limit: int


@dataclass(frozen=True)
class AttachmentFileView:
    file: AttachmentFile
    is_mine: bool


@dataclass(frozen=True)
class OfficialAttachmentView:
    attachment: OfficialAttachment
    status: AttachmentStatus
    file: AttachmentFileView | None = None
    processing: ProcessingState | None = None


@dataclass(frozen=True)
class TenderAttachmentsResult:
    official: list[OfficialAttachmentView]
    # None = la lista todavía no se sincroniza; no es lo mismo que "sin anexos".
    list_synced_at: datetime | None
    quota: UploadQuota | None = None
    can_upload: bool = False
    max_upload_size_bytes: int = MAX_ATTACHMENT_SIZE_BYTES
    processing_enabled: bool = False


class GetTenderAttachmentsUseCase:
    """La lista oficial de anexos de una licitación, con su estado para la empresa activa."""

    def __init__(
        self,
        attachments: ITenderAttachmentRepository,
        files: IAttachmentFileRepository,
        *,
        uploads_per_month: int,
        storage_available: bool,
        processing: IAttachmentProcessingStatusReader | None = None,
        processing_enabled: bool = False,
        prompt_version: str = EXTRACTION_PROMPT_VERSION,
        clock: Callable[[], datetime] = utc_now_naive,
    ) -> None:
        self.attachments = attachments
        self.files = files
        self.uploads_per_month = uploads_per_month
        self.storage_available = storage_available
        self.processing = processing
        self.processing_enabled = processing_enabled
        self.prompt_version = prompt_version
        self.clock = clock

    async def execute(
        self, tender_id: UUID, *, access: WorkspaceAccess | None = None
    ) -> TenderAttachmentsResult:
        lista = await self.attachments.get_official_list(tender_id)
        if lista is None:
            raise TenderNotFound(tender_id)

        workspace_id = access.workspace_id if access else None
        visibles = await self.files.list_visible_for_tender(
            tender_id=tender_id, workspace_id=workspace_id
        )
        por_anexo: dict[UUID, list[AttachmentFile]] = defaultdict(list)
        for archivo in visibles:
            por_anexo[archivo.tender_attachment_id].append(archivo)

        elegidos: dict[UUID, AttachmentFile | None] = {}
        for anexo in lista.attachments:
            elegidos[anexo.id] = elegir_archivo_visible(
                por_anexo.get(anexo.id, ()), workspace_id
            )

        estados_extraccion: dict[UUID, EstadoDeExtraccion] = {}
        if self.processing is not None:
            ids_archivos = [a.id for a in elegidos.values() if a is not None]
            if ids_archivos:
                estados_extraccion = await self.processing.extraction_states(
                    ids_archivos, prompt_version=self.prompt_version
                )

        official: list[OfficialAttachmentView] = []
        for anexo in lista.attachments:
            elegido = elegidos[anexo.id]
            estado_ext = (
                estados_extraccion.get(elegido.id) if elegido else None
            )
            proc_state = (
                estado_de_procesamiento(elegido, estado_ext)
                if self.processing is not None
                else None
            )
            official.append(
                OfficialAttachmentView(
                    attachment=anexo,
                    status=estado_del_anexo(elegido),
                    file=(
                        AttachmentFileView(
                            file=elegido,
                            is_mine=es_propio(elegido, workspace_id),
                        )
                        if elegido is not None
                        else None
                    ),
                    processing=proc_state,
                )
            )

        quota: UploadQuota | None = None
        if access is not None:
            usado = await self.files.get_quota_used(
                workspace_id=access.workspace_id,
                month=mes_de_cuota(self.clock()),
            )
            quota = UploadQuota(used=usado, limit=self.uploads_per_month)

        return TenderAttachmentsResult(
            official=official,
            list_synced_at=lista.synced_at,
            quota=quota,
            can_upload=bool(
                access and access.can_upload and self.storage_available
            ),
            processing_enabled=self.processing_enabled,
        )
