"""Providers del banco de capacidades y de la cotización."""

from typing import Annotated

from fastapi import Depends

from app.application.use_cases.capabilities.add_capability_evidence import (
    AddCapabilityEvidenceUseCase,
)
from app.application.use_cases.capabilities.answer_capability_question import (
    AnswerCapabilityQuestionUseCase,
)
from app.application.use_cases.capabilities.build_experience_catalog import (
    BuildExperienceCatalogUseCase,
)
from app.application.use_cases.quotation import QuotationUseCase
from app.bootstrap.repositories import (
    CapabilityAnswerRepoDep,
    CapabilityEvidenceRepoDep,
    CapabilityQuestionRepoDep,
    QuotationRepoDep,
    SupplierRepoDep,
    TenderRepoDep,
)


def get_build_experience_catalog_use_case(
    supplier_repo: SupplierRepoDep,
    question_repo: CapabilityQuestionRepoDep,
    answer_repo: CapabilityAnswerRepoDep,
    evidence_repo: CapabilityEvidenceRepoDep,
) -> BuildExperienceCatalogUseCase:
    return BuildExperienceCatalogUseCase(
        supplier_repo, question_repo, answer_repo, evidence_repo
    )


def get_answer_capability_question_use_case(
    supplier_repo: SupplierRepoDep,
    question_repo: CapabilityQuestionRepoDep,
    answer_repo: CapabilityAnswerRepoDep,
) -> AnswerCapabilityQuestionUseCase:
    return AnswerCapabilityQuestionUseCase(supplier_repo, question_repo, answer_repo)


def get_add_capability_evidence_use_case(
    supplier_repo: SupplierRepoDep,
    question_repo: CapabilityQuestionRepoDep,
    answer_repo: CapabilityAnswerRepoDep,
    evidence_repo: CapabilityEvidenceRepoDep,
) -> AddCapabilityEvidenceUseCase:
    return AddCapabilityEvidenceUseCase(
        supplier_repo, question_repo, answer_repo, evidence_repo
    )


def get_quotation_use_case(
    quotation_repo: QuotationRepoDep,
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
) -> QuotationUseCase:
    return QuotationUseCase(quotation_repo, supplier_repo, tender_repo)


CatalogUseCaseDep = Annotated[
    BuildExperienceCatalogUseCase, Depends(get_build_experience_catalog_use_case)
]


AnswerCapabilityUseCaseDep = Annotated[
    AnswerCapabilityQuestionUseCase, Depends(get_answer_capability_question_use_case)
]
