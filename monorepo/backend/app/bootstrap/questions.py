"""Providers de las preguntas inteligentes del perfil y licitaciones."""

from typing import Annotated

from fastapi import Depends

from app.application.services.smart_question_service import ISmartQuestionService
from app.application.use_cases.questions.answer_question_use_case import (
    AnswerQuestionUseCase,
)
from app.application.use_cases.questions.generate_tender_smart_questions_use_case import (
    GenerateTenderSmartQuestionsUseCase,
)
from app.application.use_cases.questions.smart_question_use_case import (
    SmartQuestionUseCase,
)
from app.bootstrap.repositories import (
    AttachmentFileRepoDep,
    QuestionRepoDep,
    SupplierRepoDep,
    TenderAttachmentRepoDep,
    TenderRepoDep,
)
from app.bootstrap.services import (
    AttachmentStorageDep,
    EmbeddingServiceDep,
    SmartQuestionAIServiceDep,
    SupplierVectorRepoDep,
)
from app.infrastructure.services.smart_question_service import SmartQuestionServiceImpl


def get_smart_question_service(question_repo: QuestionRepoDep) -> ISmartQuestionService:
    return SmartQuestionServiceImpl(question_repository=question_repo)


def get_smart_question_use_case(
    smart_question_service: Annotated[
        ISmartQuestionService, Depends(get_smart_question_service)
    ],
    supplier_repo: SupplierRepoDep,
) -> SmartQuestionUseCase:
    return SmartQuestionUseCase(
        smart_question_service=smart_question_service,
        supplier_repository=supplier_repo,
    )


def get_generate_tender_smart_questions_use_case(
    question_repo: QuestionRepoDep,
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
    ai_service: SmartQuestionAIServiceDep,
    files_repo: AttachmentFileRepoDep,
    attachments_repo: TenderAttachmentRepoDep,
    storage: AttachmentStorageDep,
) -> GenerateTenderSmartQuestionsUseCase:
    return GenerateTenderSmartQuestionsUseCase(
        question_repo=question_repo,
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        ai_service=ai_service,
        files_repo=files_repo,
        attachments_repo=attachments_repo,
        storage=storage,
    )


def get_answer_question_use_case(
    supplier_repo: SupplierRepoDep,
    question_repo: QuestionRepoDep,
    vector_repo: SupplierVectorRepoDep,
    embedding_service: EmbeddingServiceDep,
) -> AnswerQuestionUseCase:
    return AnswerQuestionUseCase(
        supplier_repo=supplier_repo,
        question_repo=question_repo,
        vector_repo=vector_repo,
        embedding_service=embedding_service,
    )
