"""Dobles en memoria de los repositorios de retroalimentación (HU-24)."""

from uuid import UUID

from app.application.repositories.feedback_repository import (
    IMatchReportRepository,
)
from app.domain.entities.feedback import (
    MatchReport,
    MatchReportKind,
)


class InMemoryMatchReportRepository(IMatchReportRepository):
    def __init__(self) -> None:
        self.reports: dict[tuple[UUID, UUID, MatchReportKind], MatchReport] = {}

    async def upsert(self, report: MatchReport) -> MatchReport:
        key = (report.supplier_id, report.tender_id, report.kind)
        existing = self.reports.get(key)
        if existing is not None:
            report = report.model_copy(update={"id": existing.id})
        self.reports[key] = report
        return report

    async def list_reported_tender_ids(
        self, supplier_id: UUID, kind: MatchReportKind
    ) -> set[UUID]:
        return {
            tender_id
            for (supplier, tender_id, report_kind) in self.reports
            if supplier == supplier_id and report_kind == kind
        }
