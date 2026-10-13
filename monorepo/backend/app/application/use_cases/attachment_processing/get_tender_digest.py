"""Caso de uso para consultar el resumen consolidado de una licitación (plan 233, decisión 4)."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.application.repositories.attachment_extraction_repository import (
    IAttachmentExtractionRepository,
)
from app.application.repositories.attachment_processing_status_reader import (
    IAttachmentProcessingStatusReader,
)
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.use_cases.attachment_processing.build_tender_digest import (
    BuildTenderDigestUseCase,
)
from app.domain.entities.attachment_extraction import EXTRACTION_PROMPT_VERSION
from app.domain.entities.attachment_file import AttachmentVisibility
from app.domain.entities.tender import Tender
from app.domain.entities.tender_digest import TenderDigest
from app.domain.errors.tender_errors import TenderNotFound
from app.domain.services.digest_consolidation import alcance_para


async def _get_tender(tenders: ITenderRepository, tender_id: UUID) -> Tender:
    encontradas = await tenders.get_tenders(TenderFilters(ids=[tender_id]))
    if not encontradas:
        raise TenderNotFound(tender_id)
    return encontradas[0]


@dataclass(frozen=True)
class TenderDigestView:
    tender_id: UUID
    digest: TenderDigest | None
    scope: Literal["shared", "workspace"]
    pending_sources: int


class GetTenderDigestUseCase:
    def __init__(
        self,
        *,
        tenders: ITenderRepository,
        extractions: IAttachmentExtractionRepository,
        status: IAttachmentProcessingStatusReader,
        build: BuildTenderDigestUseCase,
        prompt_version: str = EXTRACTION_PROMPT_VERSION,
    ) -> None:
        self.tenders = tenders
        self.extractions = extractions
        self.status = status
        self.build = build
        self.prompt_version = prompt_version

    async def execute(
        self, tender_id: UUID, *, workspace_id: UUID | None
    ) -> TenderDigestView:
        tender = await _get_tender(self.tenders, tender_id)
        fuentes = await self.extractions.list_sources(
            tender_id=tender_id,
            workspace_id=workspace_id,
            prompt_version=self.prompt_version,
        )
        alcance = alcance_para(fuentes, workspace_id)
        if alcance is None:
            fuentes = [
                f
                for f in fuentes
                if f.visibility == AttachmentVisibility.SHARED
            ]
        digest = await self.build.build_from(tender, alcance, fuentes)
        pendientes = await self.status.pending_count(
            tender_id=tender_id,
            workspace_id=workspace_id,
            prompt_version=self.prompt_version,
        )
        return TenderDigestView(
            tender_id=tender_id,
            digest=digest,
            scope="workspace" if alcance else "shared",
            pending_sources=pendientes,
        )
