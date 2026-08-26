import pytest
from uuid import uuid4

from app.application.use_cases.list_tender_chat_documents_use_case import ListTenderChatDocumentsUseCase
from app.domain.entities.tender_chat import TenderChatDocument
from tests.unit.application.fakes import InMemoryTenderChatRepository


@pytest.fixture
def repo():
    return InMemoryTenderChatRepository()


@pytest.fixture
def use_case(repo):
    return ListTenderChatDocumentsUseCase(chat_repo=repo)


@pytest.mark.asyncio
async def test_list_documents_empty(use_case):
    tender_id = uuid4()
    user_id = uuid4()
    docs = await use_case.execute(tender_id=tender_id, user_id=user_id)
    assert docs == []


@pytest.mark.asyncio
async def test_list_documents_returns_only_matching_tender_and_user(use_case, repo):
    tender_id_1 = uuid4()
    tender_id_2 = uuid4()
    user_id_1 = uuid4()
    user_id_2 = uuid4()

    doc1 = TenderChatDocument(
        tender_id=tender_id_1,
        user_id=user_id_1,
        file_name="doc1.pdf",
        file_type="pdf",
        file_size_bytes=100,
        storage_path="uploads/doc1.pdf"
    )
    doc2 = TenderChatDocument(
        tender_id=tender_id_1,
        user_id=user_id_1,
        file_name="doc2.xlsx",
        file_type="xlsx",
        file_size_bytes=200,
        storage_path="uploads/doc2.xlsx"
    )
    doc_other_tender = TenderChatDocument(
        tender_id=tender_id_2,
        user_id=user_id_1,
        file_name="other_tender.pdf",
        file_type="pdf",
        file_size_bytes=300,
        storage_path="uploads/other_tender.pdf"
    )
    doc_other_user = TenderChatDocument(
        tender_id=tender_id_1,
        user_id=user_id_2,
        file_name="other_user.pdf",
        file_type="pdf",
        file_size_bytes=400,
        storage_path="uploads/other_user.pdf"
    )

    await repo.save_document(doc1, b"1")
    await repo.save_document(doc2, b"2")
    await repo.save_document(doc_other_tender, b"3")
    await repo.save_document(doc_other_user, b"4")

    # Consultar para tender_id_1 y user_id_1
    result = await use_case.execute(tender_id=tender_id_1, user_id=user_id_1)
    assert len(result) == 2
    assert {d.file_name for d in result} == {"doc1.pdf", "doc2.xlsx"}
