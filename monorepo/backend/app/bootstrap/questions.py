"""Providers de las preguntas inteligentes del perfil."""

from typing import Annotated

from fastapi import Depends

from app.application.services.smart_question_service import ISmartQuestionService
from app.application.use_cases.questions.answer_question_use_case import (
    AnswerQuestionUseCase,
)
from app.application.use_cases.questions.smart_question_use_case import (
    SmartQuestionUseCase,
)
from app.bootstrap.repositories import QuestionRepoDep, SupplierRepoDep
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


def get_answer_question_use_case(supplier_repo: SupplierRepoDep) -> AnswerQuestionUseCase:
    # Inyectar el caso de uso que procesa las respuestas
    return AnswerQuestionUseCase(supplier_repo=supplier_repo)
