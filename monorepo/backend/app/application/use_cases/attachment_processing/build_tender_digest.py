"""Construcción de resumen consolidado de licitaciones (plan 233, decisión 4)."""

from collections.abc import Callable, Sequence
from datetime import datetime
from uuid import UUID, uuid4

from app.application.repositories.attachment_extraction_repository import (
    IAttachmentExtractionRepository,
)
from app.application.repositories.tender_digest_repository import (
    ITenderDigestRepository,
)
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.domain.entities.attachment_extraction import (
    EXTRACTION_PROMPT_VERSION,
    FuenteDeExtraccion,
)
from app.domain.entities.tender import Tender
from app.domain.entities.tender_digest import TenderDigest
from app.domain.errors.tender_errors import TenderNotFound
from app.domain.services.digest_consolidation import (
    alcance_para,
    consolidar,
    deduplicar_fuentes,
    exigir_privacidad,
    foto_de_la_api,
    huella_del_conjunto,
)
from app.shared.datetime_utils import utc_now_naive


async def _get_tender(tenders: ITenderRepository, tender_id: UUID) -> Tender:
    encontradas = await tenders.get_tenders(TenderFilters(ids=[tender_id]))
    if not encontradas:
        raise TenderNotFound(tender_id)
    return encontradas[0]


class BuildTenderDigestUseCase:
    def __init__(
        self,
        *,
        tenders: ITenderRepository,
        extractions: IAttachmentExtractionRepository,
        digests: ITenderDigestRepository,
        prompt_version: str = EXTRACTION_PROMPT_VERSION,
        clock: Callable[[], datetime] = utc_now_naive,
        new_id: Callable[[], UUID] = uuid4,
    ) -> None:
        self.tenders = tenders
        self.extractions = extractions
        self.digests = digests
        self.prompt_version = prompt_version
        self.clock = clock
        self.new_id = new_id

    async def execute(
        self, tender_id: UUID, *, workspace_id: UUID | None
    ) -> TenderDigest | None:
        tender = await _get_tender(self.tenders, tender_id)
        fuentes = await self.extractions.list_sources(
            tender_id=tender_id,
            workspace_id=workspace_id,
            prompt_version=self.prompt_version,
        )
        if workspace_id is not None and alcance_para(fuentes, workspace_id) is None:
            # La empresa ya no tiene privados (los borró o se compartieron): su vista es la compartida.
            await self.digests.retire_current(tender_id, workspace_id)
            return None
        return await self.build_from(tender, workspace_id, fuentes)

    async def build_from(
        self,
        tender: Tender,
        alcance: UUID | None,
        fuentes: Sequence[FuenteDeExtraccion],
    ) -> TenderDigest | None:
        fuentes = deduplicar_fuentes(fuentes)
        exigir_privacidad(fuentes, alcance)
        huella = huella_del_conjunto(fuentes)
        foto = foto_de_la_api(tender)
        actual = await self.digests.get_current(tender.id, alcance)
        if (
            actual
            and actual.extraction_set_hash == huella
            and actual.api_snapshot == foto
        ):
            return actual
        if not fuentes and actual is None:
            return None
        nuevo = TenderDigest(
            id=self.new_id(),
            tender_id=tender.id,
            workspace_id=alcance,
            version=(actual.version + 1) if actual else 1,
            extraction_set_hash=huella,
            is_current=True,
            source_count=len(fuentes),
            data=consolidar(fuentes, tender),
            api_snapshot=foto,
            created_at=self.clock(),
        )
        return await self.digests.replace_current(
            nuevo, previous_id=actual.id if actual else None
        )
