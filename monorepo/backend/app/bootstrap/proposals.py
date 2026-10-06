"""Providers del borrador de postulación."""

from typing import Annotated

from fastapi import Depends

from app.application.use_cases.capabilities.list_pending_questions import (
    ListPendingCapabilityQuestionsUseCase,
)
from app.application.use_cases.proposals.answer_proposal_question import (
    AnswerProposalQuestionUseCase,
)
from app.application.use_cases.proposals.decide_discrepancy import (
    DecideDiscrepancyUseCase,
)
from app.application.use_cases.proposals.export_proposal import (
    ExportProposalDocxUseCase,
)
from app.application.use_cases.proposals.generate_proposal import (
    GenerateProposalUseCase,
)
from app.application.use_cases.proposals.get_proposal import GetProposalUseCase
from app.application.use_cases.proposals.regenerate_proposal import (
    RegenerateProposalUseCase,
)
from app.application.use_cases.proposals.resume_proposal import ResumeProposalUseCase
from app.application.use_cases.proposals.start_feasibility import (
    StartFeasibilityUseCase,
)
from app.application.use_cases.proposals.sync_proposal_answers import (
    SyncProposalAnswersUseCase,
)
from app.bootstrap.capabilities import AnswerCapabilityUseCaseDep, CatalogUseCaseDep
from app.bootstrap.repositories import (
    CapabilityAnswerRepoDep,
    CapabilityQuestionRepoDep,
    ProposalDraftRepoDep,
    SupplierRepoDep,
    TenderChatRepoDep,
    TenderRepoDep,
)
from app.bootstrap.services import DocumentValidatorDep, ProposalAIServiceDep
from app.infrastructure.services.docx_proposal_exporter import DocxProposalExporter


def get_list_pending_capability_questions_use_case(
    supplier_repo: SupplierRepoDep,
    question_repo: CapabilityQuestionRepoDep,
    answer_repo: CapabilityAnswerRepoDep,
    tender_repo: TenderRepoDep,
) -> ListPendingCapabilityQuestionsUseCase:
    return ListPendingCapabilityQuestionsUseCase(
        supplier_repo, question_repo, answer_repo, tender_repo
    )


def get_start_feasibility_use_case(
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
    draft_repo: ProposalDraftRepoDep,
    question_repo: CapabilityQuestionRepoDep,
    answer_repo: CapabilityAnswerRepoDep,
    catalog_use_case: CatalogUseCaseDep,
    chat_repo: TenderChatRepoDep,
    ai_service: ProposalAIServiceDep,
    validator: DocumentValidatorDep,
) -> StartFeasibilityUseCase:
    return StartFeasibilityUseCase(
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        draft_repo=draft_repo,
        question_repo=question_repo,
        answer_repo=answer_repo,
        catalog_use_case=catalog_use_case,
        chat_repo=chat_repo,
        ai_service=ai_service,
        validator_service=validator,
    )


def get_proposal_use_case(
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
    draft_repo: ProposalDraftRepoDep,
    question_repo: CapabilityQuestionRepoDep,
    catalog_use_case: CatalogUseCaseDep,
) -> GetProposalUseCase:
    return GetProposalUseCase(
        supplier_repo, tender_repo, draft_repo, question_repo, catalog_use_case
    )


def get_answer_proposal_question_use_case(
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
    draft_repo: ProposalDraftRepoDep,
    question_repo: CapabilityQuestionRepoDep,
    answer_use_case: AnswerCapabilityUseCaseDep,
) -> AnswerProposalQuestionUseCase:
    return AnswerProposalQuestionUseCase(
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        draft_repo=draft_repo,
        question_repo=question_repo,
        answer_use_case=answer_use_case,
    )


def get_decide_discrepancy_use_case(
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
    draft_repo: ProposalDraftRepoDep,
) -> DecideDiscrepancyUseCase:
    return DecideDiscrepancyUseCase(supplier_repo, tender_repo, draft_repo)


def get_generate_proposal_use_case(
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
    draft_repo: ProposalDraftRepoDep,
    catalog_use_case: CatalogUseCaseDep,
    chat_repo: TenderChatRepoDep,
    ai_service: ProposalAIServiceDep,
    validator: DocumentValidatorDep,
) -> GenerateProposalUseCase:
    return GenerateProposalUseCase(
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        draft_repo=draft_repo,
        catalog_use_case=catalog_use_case,
        chat_repo=chat_repo,
        ai_service=ai_service,
        validator_service=validator,
    )


GenerateProposalUseCaseDep = Annotated[
    GenerateProposalUseCase, Depends(get_generate_proposal_use_case)
]


def get_regenerate_proposal_use_case(
    generate_use_case: GenerateProposalUseCaseDep,
) -> RegenerateProposalUseCase:
    return RegenerateProposalUseCase(generate_use_case)


def get_sync_proposal_answers_use_case(
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
    draft_repo: ProposalDraftRepoDep,
    catalog_use_case: CatalogUseCaseDep,
    generate_use_case: GenerateProposalUseCaseDep,
) -> SyncProposalAnswersUseCase:
    return SyncProposalAnswersUseCase(
        supplier_repo, tender_repo, draft_repo, catalog_use_case, generate_use_case
    )


def get_export_proposal_use_case(
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
    draft_repo: ProposalDraftRepoDep,
) -> ExportProposalDocxUseCase:
    return ExportProposalDocxUseCase(
        supplier_repo, tender_repo, draft_repo, DocxProposalExporter()
    )


def get_resume_proposal_use_case(
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
    draft_repo: ProposalDraftRepoDep,
) -> ResumeProposalUseCase:
    return ResumeProposalUseCase(supplier_repo, tender_repo, draft_repo)
