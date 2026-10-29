from uuid import UUID

from app.application.repositories.feedback_repository import IMatchReportRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.use_cases.supplier.resolver_empresa import resolver_empresa
from app.domain.entities.feedback import MatchReport, MatchReportKind
from app.domain.errors.supplier_errors import SupplierNotFoundForUser
from app.domain.errors.tender_errors import TenderNotFound


class ReportMatchUseCase:
    """Una empresa reporta un mal match o un análisis de compatibilidad incorrecto.

    El reporte es por empresa y no por usuario: lo que el equipo reporta vale para
    todos sus miembros. Reportar de nuevo la misma licitación reemplaza el motivo.
    """

    def __init__(
        self,
        match_report_repo: IMatchReportRepository,
        tender_repo: ITenderRepository,
        supplier_repo: ISupplierRepository,
    ):
        self.match_report_repo = match_report_repo
        self.tender_repo = tender_repo
        self.supplier_repo = supplier_repo

    async def execute(
        self,
        user_id: UUID,
        supplier_id: UUID | None,
        tender_id: UUID,
        kind: MatchReportKind,
        reason: str,
    ) -> MatchReport:
        supplier = await resolver_empresa(self.supplier_repo, user_id, supplier_id)
        if supplier is None:
            raise SupplierNotFoundForUser(user_id)
        if not await self.tender_repo.get_tenders(TenderFilters(ids=[tender_id])):
            raise TenderNotFound(tender_id)
        return await self.match_report_repo.upsert(
            MatchReport(
                supplier_id=supplier.id,
                user_id=user_id,
                tender_id=tender_id,
                kind=kind,
                reason=reason,
            )
        )
