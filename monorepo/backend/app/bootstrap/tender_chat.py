"""Providers del asistente de licitaciones."""

from typing import Annotated

from fastapi import Depends

from app.application.services.tender_assistant_ai_service import (
    ITenderAssistantAIService,
)
from app.application.use_cases.ask_tender_assistant_use_case import (
    AskTenderAssistantUseCase,
)
from app.application.use_cases.create_tender_chat_session_use_case import (
    CreateTenderChatSessionUseCase,
)
from app.application.use_cases.delete_tender_chat_document_use_case import (
    DeleteTenderChatDocumentUseCase,
)
from app.application.use_cases.get_tender_chat_history_use_case import (
    GetTenderChatHistoryUseCase,
)
from app.application.use_cases.list_tender_chat_documents_use_case import (
    ListTenderChatDocumentsUseCase,
)
from app.application.use_cases.upload_tender_chat_document_use_case import (
    UploadTenderChatDocumentUseCase,
)
from app.bootstrap.repositories import (
    AttachmentExtractionRepoDep,
    AttachmentFileRepoDep,
    GeminiUsageRepoDep,
    MatchingResultRepoDep,
    QuotationRepoDep,
    SupplierRepoDep,
    TenderAttachmentRepoDep,
    TenderChatRepoDep,
    TenderDigestRepoDep,
    TenderRepoDep,
)
from app.bootstrap.services import (
    AttachmentStorageDep,
    DocumentAnalysisQuotationServiceDep,
    DocumentValidatorDep,
    MilestoneExtractionBackgroundDep,
    get_tender_assistant_ai_service,
)


def get_upload_tender_chat_doc_use_case(
    chat_repo: TenderChatRepoDep,
    validator_service: DocumentValidatorDep,
    milestone_extraction: MilestoneExtractionBackgroundDep,
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
    quotation_repo: QuotationRepoDep,
    matching_result_repo: MatchingResultRepoDep,
    unified_service: DocumentAnalysisQuotationServiceDep,
) -> UploadTenderChatDocumentUseCase:
    return UploadTenderChatDocumentUseCase(
        chat_repo=chat_repo,
        validator_service=validator_service,
        milestone_extraction=milestone_extraction,
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        quotation_repo=quotation_repo,
        matching_result_repo=matching_result_repo,
        unified_service=unified_service,
    )


def get_list_tender_chat_docs_use_case(
    chat_repo: TenderChatRepoDep,
) -> ListTenderChatDocumentsUseCase:
    return ListTenderChatDocumentsUseCase(chat_repo=chat_repo)


def get_delete_tender_chat_doc_use_case(
    chat_repo: TenderChatRepoDep,
) -> DeleteTenderChatDocumentUseCase:
    return DeleteTenderChatDocumentUseCase(chat_repo=chat_repo)


def get_ask_tender_assistant_use_case(
    chat_repo: TenderChatRepoDep,
    ai_service: Annotated[
        ITenderAssistantAIService, Depends(get_tender_assistant_ai_service)
    ],
    supplier_repo: SupplierRepoDep,
    tender_repo: TenderRepoDep,
    validator_service: DocumentValidatorDep,
    digest_repo: TenderDigestRepoDep,
    extraction_repo: AttachmentExtractionRepoDep,
    attachment_file_repo: AttachmentFileRepoDep,
    attachment_storage: AttachmentStorageDep,
    usage_repo: GeminiUsageRepoDep,
    tender_attachment_repo: TenderAttachmentRepoDep,
) -> AskTenderAssistantUseCase:
    return AskTenderAssistantUseCase(
        chat_repo=chat_repo,
        ai_service=ai_service,
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        validator_service=validator_service,
        digest_repo=digest_repo,
        extraction_repo=extraction_repo,
        attachment_file_repo=attachment_file_repo,
        attachment_storage=attachment_storage,
        usage_repo=usage_repo,
        tender_attachment_repo=tender_attachment_repo,
    )


def get_create_tender_chat_session_use_case(
    chat_repo: TenderChatRepoDep,
) -> CreateTenderChatSessionUseCase:
    return CreateTenderChatSessionUseCase(chat_repo=chat_repo)


def get_tender_chat_history_use_case(
    chat_repo: TenderChatRepoDep,
) -> GetTenderChatHistoryUseCase:
    return GetTenderChatHistoryUseCase(chat_repo=chat_repo)
