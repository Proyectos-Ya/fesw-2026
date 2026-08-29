import pytest
from uuid import uuid4

from app.application.use_cases.delete_tender_chat_document_use_case import DeleteTenderChatDocumentUseCase
from app.domain.entities.tender_chat import TenderChatDocument
from app.domain.errors.tender_chat_errors import DocumentNotFoundError
from tests.unit.application.fakes import InMemoryTenderChatRepository


@pytest.fixture
def repo():
    return InMemoryTenderChatRepository()


@pytest.fixture
def use_case(repo):
    return DeleteTenderChatDocumentUseCase(chat_repo=repo)


@pytest.mark.asyncio
async def test_delete_existing_document_success(use_case, repo):
    tender_id = uuid4()
    user_id = uuid4()
    doc_id = uuid4()

    doc = TenderChatDocument(
        id=doc_id,
        tender_id=tender_id,
        user_id=user_id,
        file_name="bases.pdf",
        file_type="pdf",
        file_size_bytes=1024,
        storage_path="uploads/bases.pdf"
    )
    await repo.save_document(doc, b"dummy content")

    # Ejecutar eliminación
    result = await use_case.execute(document_id=doc_id, user_id=user_id)
    assert result is True

    # Verificar que ya no existe en el repositorio
    remaining_docs = await repo.get_documents_by_chat(user_id=user_id, tender_id=tender_id)
    assert len(remaining_docs) == 0


@pytest.mark.asyncio
async def test_delete_non_existent_document_raises_not_found(use_case):
    non_existent_id = uuid4()
    user_id = uuid4()

    with pytest.raises(DocumentNotFoundError):
        await use_case.execute(document_id=non_existent_id, user_id=user_id)


@pytest.mark.asyncio
async def test_delete_document_owned_by_another_user_raises_not_found(use_case, repo):
    tender_id = uuid4()
    owner_user_id = uuid4()
    other_user_id = uuid4()
    doc_id = uuid4()

    doc = TenderChatDocument(
        id=doc_id,
        tender_id=tender_id,
        user_id=owner_user_id,
        file_name="privado.pdf",
        file_type="pdf",
        file_size_bytes=2048,
        storage_path="uploads/privado.pdf"
    )
    await repo.save_document(doc, b"private content")

    # Intentar eliminar con otro usuario debe fallar
    with pytest.raises(DocumentNotFoundError):
        await use_case.execute(document_id=doc_id, user_id=other_user_id)

    # El documento original debe seguir existiendo para el dueño
    docs = await repo.get_documents_by_chat(user_id=owner_user_id, tender_id=tender_id)
    assert len(docs) == 1
