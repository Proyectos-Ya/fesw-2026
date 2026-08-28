import pytest
from uuid import uuid4

from app.application.use_cases.upload_tender_chat_document_use_case import UploadTenderChatDocumentUseCase
from app.domain.entities.tender_chat import TenderChatDocument
from app.domain.errors.tender_chat_errors import (
    UnsupportedDocumentTypeError,
    MaxDocumentsExceededError,
    TenderChatError,
)
from tests.unit.application.fakes import InMemoryTenderChatRepository


@pytest.fixture
def repo():
    return InMemoryTenderChatRepository()


@pytest.fixture
def use_case(repo):
    return UploadTenderChatDocumentUseCase(chat_repo=repo)


@pytest.mark.asyncio
async def test_upload_pdf_success(use_case, repo):
    tender_id = uuid4()
    user_id = uuid4()
    pdf_bytes = b"%PDF-1.4 sample content"
    
    doc = await use_case.execute(
        tender_id=tender_id,
        user_id=user_id,
        file_name="Bases_Administrativas.pdf",
        file_bytes=pdf_bytes
    )

    assert isinstance(doc, TenderChatDocument)
    assert doc.tender_id == tender_id
    assert doc.user_id == user_id
    assert doc.file_name == "Bases_Administrativas.pdf"
    assert doc.file_type == "pdf"
    assert doc.file_size_bytes == len(pdf_bytes)
    
    # Verificar persistencia en el repo
    saved_bytes = await repo.get_document_bytes(doc.id, user_id)
    assert saved_bytes == pdf_bytes


@pytest.mark.asyncio
@pytest.mark.parametrize("file_name, expected_type", [
    ("catalogo_productos.xlsx", "xlsx"),
    ("diagrama_arquitectura.PNG", "png"),
    ("documento.PDF", "pdf")
])
async def test_upload_allowed_formats_success(use_case, file_name, expected_type):
    tender_id = uuid4()
    user_id = uuid4()
    
    doc = await use_case.execute(
        tender_id=tender_id,
        user_id=user_id,
        file_name=file_name,
        file_bytes=b"sample binary content"
    )

    assert doc.file_type == expected_type.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_file_name", [
    ("malware.exe"),
    ("comprimido.zip"),
    ("documento.docx"),
    ("script.sh"),
    ("sin_extension"),
    ("archivo.tar.gz")
])
async def test_upload_unsupported_extension_raises_error(use_case, invalid_file_name):
    tender_id = uuid4()
    user_id = uuid4()
    
    with pytest.raises(UnsupportedDocumentTypeError):
        await use_case.execute(
            tender_id=tender_id,
            user_id=user_id,
            file_name=invalid_file_name,
            file_bytes=b"dummy content"
        )


@pytest.mark.asyncio
async def test_upload_empty_file_raises_error(use_case):
    tender_id = uuid4()
    user_id = uuid4()
    
    with pytest.raises(ValueError, match="archivo está vacío"):
        await use_case.execute(
            tender_id=tender_id,
            user_id=user_id,
            file_name="archivo_vacio.pdf",
            file_bytes=b""
        )


@pytest.mark.asyncio
async def test_upload_exceeding_max_size_raises_error(use_case):
    tender_id = uuid4()
    user_id = uuid4()
    # 21 MB (límite 20 MB)
    large_bytes = b"0" * (21 * 1024 * 1024)
    
    with pytest.raises(ValueError, match="excede el tamaño máximo"):
        await use_case.execute(
            tender_id=tender_id,
            user_id=user_id,
            file_name="archivo_grande.pdf",
            file_bytes=large_bytes
        )


@pytest.mark.asyncio
async def test_upload_exceeding_max_documents_per_chat_raises_error(use_case):
    tender_id = uuid4()
    user_id = uuid4()
    
    # Subir 5 documentos (máximo permitido)
    for i in range(5):
        await use_case.execute(
            tender_id=tender_id,
            user_id=user_id,
            file_name=f"doc_{i}.pdf",
            file_bytes=b"content"
        )
    
    # El 6to debe lanzar MaxDocumentsExceededError
    with pytest.raises(MaxDocumentsExceededError):
        await use_case.execute(
            tender_id=tender_id,
            user_id=user_id,
            file_name="doc_extra.pdf",
            file_bytes=b"content"
        )
