from typing import Annotated

from fastapi import Depends

from app.application.use_cases.feedback.report_match import ReportMatchUseCase
from app.application.use_cases.feedback.submit_app_feedback import (
    SubmitAppFeedbackUseCase,
)
from app.application.use_cases.feedback.submit_assistant_dislike import (
    SubmitAssistantDislikeUseCase,
)
from app.bootstrap.repositories import (
    AppFeedbackRepoDep,
    AssistantFeedbackRepoDep,
    MatchReportRepoDep,
    SupplierRepoDep,
    TenderChatRepoDep,
    TenderRepoDep,
)


def get_report_match_use_case(
    match_report_repo: MatchReportRepoDep,
    tender_repo: TenderRepoDep,
    supplier_repo: SupplierRepoDep,
) -> ReportMatchUseCase:
    return ReportMatchUseCase(
        match_report_repo=match_report_repo,
        tender_repo=tender_repo,
        supplier_repo=supplier_repo,
    )


ReportMatchUseCaseDep = Annotated[
    ReportMatchUseCase, Depends(get_report_match_use_case)
]


def get_submit_assistant_dislike_use_case(
    assistant_feedback_repo: AssistantFeedbackRepoDep,
    chat_repo: TenderChatRepoDep,
    supplier_repo: SupplierRepoDep,
) -> SubmitAssistantDislikeUseCase:
    return SubmitAssistantDislikeUseCase(
        assistant_feedback_repo=assistant_feedback_repo,
        chat_repo=chat_repo,
        supplier_repo=supplier_repo,
    )


SubmitAssistantDislikeUseCaseDep = Annotated[
    SubmitAssistantDislikeUseCase, Depends(get_submit_assistant_dislike_use_case)
]


def get_submit_app_feedback_use_case(
    app_feedback_repo: AppFeedbackRepoDep,
) -> SubmitAppFeedbackUseCase:
    return SubmitAppFeedbackUseCase(app_feedback_repo=app_feedback_repo)


SubmitAppFeedbackUseCaseDep = Annotated[
    SubmitAppFeedbackUseCase, Depends(get_submit_app_feedback_use_case)
]
