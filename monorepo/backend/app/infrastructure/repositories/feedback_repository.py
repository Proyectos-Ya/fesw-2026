from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.feedback_repository import (
    IAppFeedbackRepository,
    IAssistantFeedbackRepository,
    IMatchReportRepository,
)
from app.domain.entities.feedback import (
    AppFeedback,
    AppFeedbackKind,
    AssistantMessageFeedback,
    MatchReport,
    MatchReportKind,
)
from app.infrastructure.repositories.feedback_model import (
    AppFeedbackModel,
    AssistantMessageFeedbackModel,
    MatchReportModel,
)


class MatchReportRepository(IMatchReportRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_entity(model: MatchReportModel) -> MatchReport:
        return MatchReport(
            id=model.id,
            supplier_id=model.supplier_id,
            user_id=model.user_id,
            tender_id=model.tender_id,
            kind=MatchReportKind(model.kind),
            reason=model.reason,
            created_at=model.created_at,
        )

    async def upsert(self, report: MatchReport) -> MatchReport:
        result = await self.session.exec(
            select(MatchReportModel).where(
                MatchReportModel.supplier_id == report.supplier_id,
                MatchReportModel.tender_id == report.tender_id,
                MatchReportModel.kind == report.kind.value,
            )
        )
        model = result.first()
        if model is None:
            model = MatchReportModel(
                id=report.id,
                supplier_id=report.supplier_id,
                user_id=report.user_id,
                tender_id=report.tender_id,
                kind=report.kind.value,
                reason=report.reason,
                created_at=report.created_at,
            )
        else:
            model.user_id = report.user_id
            model.reason = report.reason
            model.created_at = report.created_at
        self.session.add(model)
        await self.session.commit()
        return self._to_entity(model)

    async def list_reported_tender_ids(
        self, supplier_id: UUID, kind: MatchReportKind
    ) -> set[UUID]:
        result = await self.session.exec(
            select(MatchReportModel.tender_id).where(
                MatchReportModel.supplier_id == supplier_id,
                MatchReportModel.kind == kind.value,
            )
        )
        return set(result.all())


class AssistantFeedbackRepository(IAssistantFeedbackRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_entity(model: AssistantMessageFeedbackModel) -> AssistantMessageFeedback:
        return AssistantMessageFeedback(
            id=model.id,
            message_id=model.message_id,
            user_id=model.user_id,
            supplier_id=model.supplier_id,
            tender_id=model.tender_id,
            reason=model.reason,
            created_at=model.created_at,
        )

    async def _get_model(
        self, message_id: UUID, user_id: UUID
    ) -> AssistantMessageFeedbackModel | None:
        result = await self.session.exec(
            select(AssistantMessageFeedbackModel).where(
                AssistantMessageFeedbackModel.message_id == message_id,
                AssistantMessageFeedbackModel.user_id == user_id,
            )
        )
        return result.first()

    async def upsert(
        self, feedback: AssistantMessageFeedback
    ) -> AssistantMessageFeedback:
        model = await self._get_model(feedback.message_id, feedback.user_id)
        if model is None:
            model = AssistantMessageFeedbackModel(
                id=feedback.id,
                message_id=feedback.message_id,
                user_id=feedback.user_id,
                supplier_id=feedback.supplier_id,
                tender_id=feedback.tender_id,
                reason=feedback.reason,
                created_at=feedback.created_at,
            )
        else:
            model.supplier_id = feedback.supplier_id
            model.reason = feedback.reason
            model.created_at = feedback.created_at
        self.session.add(model)
        await self.session.commit()
        return self._to_entity(model)

    async def get_by_message(
        self, message_id: UUID, user_id: UUID
    ) -> AssistantMessageFeedback | None:
        model = await self._get_model(message_id, user_id)
        return self._to_entity(model) if model else None


class AppFeedbackRepository(IAppFeedbackRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, feedback: AppFeedback) -> AppFeedback:
        self.session.add(
            AppFeedbackModel(
                id=feedback.id,
                user_id=feedback.user_id,
                kind=feedback.kind.value,
                message=feedback.message,
                rating=feedback.rating,
                anonymous=feedback.anonymous,
                created_at=feedback.created_at,
            )
        )
        await self.session.commit()
        return feedback


__all__ = [
    "AppFeedbackKind",
    "AppFeedbackRepository",
    "AssistantFeedbackRepository",
    "MatchReportRepository",
]
