from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from app.application.repositories.matching_result_repository import (
    IMatchingResultRepository,
)
from app.application.repositories.quotation_repository import IQuotationRepository
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.use_cases.exports.export_snapshot import (
    ExportSnapshot,
    key_dates_for,
)
from app.domain.entities.supplier_member import WorkspaceContext
from app.domain.errors.export_errors import ExportForbidden
from app.domain.errors.tender_errors import TenderNotFound
from app.shared.datetime_utils import utc_now_naive

# Exportar muestra lo mismo que la ficha, así que exige lo mismo que verla.
_PERMISO_EXPORTAR = "view_matches"


class BuildExportSnapshotUseCase:
    """Reúne lo que va en el PDF y el Excel, de la empresa activa del selector.

    Solo lee: nunca calcula un puntaje ni genera un análisis. Exportar es dejar
    constancia de lo que hay, no disparar inferencias.
    """

    def __init__(
        self,
        tenders: ITenderRepository,
        matching_results: IMatchingResultRepository,
        quotations: IQuotationRepository,
        now: Callable[[], datetime] = utc_now_naive,
    ) -> None:
        self.tenders = tenders
        self.matching_results = matching_results
        self.quotations = quotations
        self.now = now

    async def execute(self, ctx: WorkspaceContext, tender_id: UUID) -> ExportSnapshot:
        if _PERMISO_EXPORTAR not in ctx.permissions:
            raise ExportForbidden()
        encontradas = await self.tenders.get_tenders(TenderFilters(ids=[tender_id]))
        if not encontradas:
            raise TenderNotFound(tender_id)
        tender = encontradas[0]
        empresa = ctx.active_supplier_id

        match = await self.matching_results.get_by_proveedor_and_licitacion(empresa, tender_id)
        score = match.final_score if match is not None else None

        return ExportSnapshot(
            tender=tender,
            supplier_name=ctx.active_supplier_name,
            score_pct=round(score * 100) if score is not None else None,
            analysis=await self.tenders.get_deep_analysis(tender_id, empresa),
            quotation=await self.quotations.get(empresa, tender_id),
            key_dates=key_dates_for(tender),
            generated_at=self.now(),
        )
