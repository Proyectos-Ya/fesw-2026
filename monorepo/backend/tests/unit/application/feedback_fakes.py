"""Dobles en memoria de los repositorios de retroalimentación (HU-24)."""

from uuid import UUID

from app.application.repositories.feedback_repository import (
    IAssistantFeedbackRepository,
    IMatchReportRepository,
)
from app.domain.entities.feedback import (
    AssistantMessageFeedback,
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


class InMemoryAssistantFeedbackRepository(IAssistantFeedbackRepository):
    def __init__(self) -> None:
        self.feedbacks: dict[tuple[UUID, UUID], AssistantMessageFeedback] = {}

    async def upsert(
        self, feedback: AssistantMessageFeedback
    ) -> AssistantMessageFeedback:
        key = (feedback.message_id, feedback.user_id)
        existing = self.feedbacks.get(key)
        if existing is not None:
            feedback = feedback.model_copy(update={"id": existing.id})
        self.feedbacks[key] = feedback
        return feedback

    async def get_by_message(
        self, message_id: UUID, user_id: UUID
    ) -> AssistantMessageFeedback | None:
        return self.feedbacks.get((message_id, user_id))

    async def list_by_tender_and_supplier(
        self, tender_id: UUID, supplier_id: UUID
    ) -> list[AssistantMessageFeedback]:
        return [
            fb
            for fb in self.feedbacks.values()
            if fb.tender_id == tender_id and fb.supplier_id == supplier_id
        ]
