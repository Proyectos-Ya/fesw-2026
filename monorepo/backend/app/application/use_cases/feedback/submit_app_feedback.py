from uuid import UUID

from app.application.repositories.feedback_repository import IAppFeedbackRepository
from app.domain.entities.feedback import AppFeedback, AppFeedbackKind


class SubmitAppFeedbackUseCase:
    """Registra comentarios, quejas y reseñas del sistema ingresados en la sección de ajustes (HU-24)."""

    def __init__(self, app_feedback_repo: IAppFeedbackRepository) -> None:
        self.app_feedback_repo = app_feedback_repo

    async def submit_comment(self, user_id: UUID, message: str) -> AppFeedback:
        feedback = AppFeedback(
            user_id=user_id,
            kind=AppFeedbackKind.COMMENT,
            message=message,
        )
        return await self.app_feedback_repo.add(feedback)

    async def submit_review(
        self,
        user_id: UUID,
        rating: int | None = None,
        message: str | None = None,
        anonymous: bool = False,
    ) -> AppFeedback:
        feedback = AppFeedback(
            user_id=user_id,
            kind=AppFeedbackKind.REVIEW,
            rating=rating,
            message=message,
            anonymous=anonymous,
        )
        return await self.app_feedback_repo.add(feedback)
