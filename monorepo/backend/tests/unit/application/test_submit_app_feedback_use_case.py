from uuid import uuid4
import pytest
from app.application.use_cases.feedback.submit_app_feedback import SubmitAppFeedbackUseCase
from app.domain.entities.feedback import AppFeedbackKind
from tests.unit.application.feedback_fakes import InMemoryAppFeedbackRepository


@pytest.mark.asyncio
async def test_submit_comment_success():
    repo = InMemoryAppFeedbackRepository()
    use_case = SubmitAppFeedbackUseCase(app_feedback_repo=repo)
    user_id = uuid4()

    res = await use_case.submit_comment(user_id=user_id, message="Excelente sistema, pero falta modo oscuro.")

    assert res.user_id == user_id
    assert res.kind == AppFeedbackKind.COMMENT
    assert res.message == "Excelente sistema, pero falta modo oscuro."
    assert res.rating is None
    assert len(repo.feedbacks) == 1


@pytest.mark.asyncio
async def test_submit_review_with_stars_and_comment_and_anonymity():
    repo = InMemoryAppFeedbackRepository()
    use_case = SubmitAppFeedbackUseCase(app_feedback_repo=repo)
    user_id = uuid4()

    res = await use_case.submit_review(
        user_id=user_id,
        rating=5,
        message="Nos ha ayudado a ganar 3 licitaciones.",
        anonymous=True,
    )

    assert res.user_id == user_id
    assert res.kind == AppFeedbackKind.REVIEW
    assert res.rating == 5
    assert res.message == "Nos ha ayudado a ganar 3 licitaciones."
    assert res.anonymous is True
    assert len(repo.feedbacks) == 1


@pytest.mark.asyncio
async def test_submit_review_only_stars_allowed():
    repo = InMemoryAppFeedbackRepository()
    use_case = SubmitAppFeedbackUseCase(app_feedback_repo=repo)
    user_id = uuid4()

    res = await use_case.submit_review(user_id=user_id, rating=0, anonymous=False)
    assert res.rating == 0
    assert res.message is None
