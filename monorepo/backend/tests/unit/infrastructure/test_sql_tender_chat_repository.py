import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone

from app.domain.entities.tender_chat import (
    TenderChatMessage,
    TenderChatDocument,
    Citation,
)
from app.infrastructure.repositories.sql_tender_chat_repository import SQLTenderChatRepository
from app.infrastructure.repositories.tender_chat_model import (
    TenderChatMessageModel,
    TenderChatDocumentModel,
)


@pytest.fixture
def mock_session():
    session = AsyncMock()
    return session


@pytest.fixture
def repo(mock_session, tmp_path):
    return SQLTenderChatRepository(session=mock_session, storage_dir=tmp_path)


@pytest.mark.asyncio
async def test_save_message_adds_model_and_commits(repo, mock_session):
    msg = TenderChatMessage(
        session_id=uuid4(),
        tender_id=uuid4(),
        user_id=uuid4(),
        role="assistant",
        content="Respuesta",
        citations=[Citation(document_name="bases.pdf", quote="cita")]
    )

    saved = await repo.save_message(msg)

    assert saved.id == msg.id
    assert saved.content == "Respuesta"
    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited_once()



@pytest.mark.asyncio
async def test_get_history_queries_ordered_messages(repo, mock_session):
    tender_id = uuid4()
    user_id = uuid4()

    model1 = TenderChatMessageModel(
        id=uuid4(),
        tender_id=tender_id,
        user_id=user_id,
        role="user",
        content="Pregunta",
        citations=[],
        created_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    model2 = TenderChatMessageModel(
        id=uuid4(),
        tender_id=tender_id,
        user_id=user_id,
        role="assistant",
        content="Respuesta",
        citations=[{"document_name": "bases.pdf", "page_or_sheet": "1", "quote": "txt"}],
        created_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )

    mock_exec_result = MagicMock()
    mock_exec_result.all.return_value = [model1, model2]
    mock_session.exec.return_value = mock_exec_result

    history = await repo.get_history(user_id=user_id, tender_id=tender_id, limit=10)

    assert len(history) == 2
    assert history[0].role == "user"
    assert history[1].role == "assistant"
    assert len(history[1].citations) == 1
    assert history[1].citations[0].document_name == "bases.pdf"


@pytest.mark.asyncio
async def test_save_and_get_document_bytes_with_storage(repo, mock_session, tmp_path):
    tender_id = uuid4()
    user_id = uuid4()
    doc_id = uuid4()
    file_bytes = b"%PDF-1.4 sample stream"

    doc = TenderChatDocument(
        id=doc_id,
        tender_id=tender_id,
        user_id=user_id,
        file_name="especificaciones.pdf",
        file_type="pdf",
        file_size_bytes=len(file_bytes),
        storage_path="uploads/temp/especificaciones.pdf"
    )

    saved_doc = await repo.save_document(doc, file_bytes)

    assert saved_doc.id == doc_id
    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited_once()

    # Mock DB query for get_document_bytes
    doc_model = TenderChatDocumentModel(
        id=doc_id,
        tender_id=tender_id,
        user_id=user_id,
        file_name="especificaciones.pdf",
        file_type="pdf",
        file_size_bytes=len(file_bytes),
        storage_path=saved_doc.storage_path,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    mock_exec_result = MagicMock()
    mock_exec_result.first.return_value = doc_model
    mock_session.exec.return_value = mock_exec_result

    retrieved_bytes = await repo.get_document_bytes(document_id=doc_id, user_id=user_id)
    assert retrieved_bytes == file_bytes


@pytest.mark.asyncio
async def test_delete_document_removes_file_and_model(repo, mock_session, tmp_path):
    tender_id = uuid4()
    user_id = uuid4()
    doc_id = uuid4()
    file_bytes = b"sample data"

    doc = TenderChatDocument(
        id=doc_id,
        tender_id=tender_id,
        user_id=user_id,
        file_name="archivo.pdf",
        file_type="pdf",
        file_size_bytes=len(file_bytes),
        storage_path="uploads/temp/archivo.pdf"
    )
    saved_doc = await repo.save_document(doc, file_bytes)


    # Mock DB query for delete
    doc_model = TenderChatDocumentModel(
        id=doc_id,
        tender_id=tender_id,
        user_id=user_id,
        file_name="archivo.pdf",
        file_type="pdf",
        file_size_bytes=len(file_bytes),
        storage_path=saved_doc.storage_path,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    mock_exec_result = MagicMock()
    mock_exec_result.first.return_value = doc_model
    mock_session.exec.return_value = mock_exec_result

    success = await repo.delete_document(document_id=doc_id, user_id=user_id)
    assert success is True
    mock_session.delete.assert_called_once_with(doc_model)
    mock_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_create_session_deactivates_older_and_creates_new(repo, mock_session):
    from app.infrastructure.repositories.tender_chat_model import TenderChatSessionModel

    tender_id = uuid4()
    user_id = uuid4()

    older_model = TenderChatSessionModel(
        id=uuid4(),
        tender_id=tender_id,
        user_id=user_id,
        is_active=True,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    mock_exec_result = MagicMock()
    mock_exec_result.all.return_value = [older_model]
    mock_session.exec.return_value = mock_exec_result

    new_session = await repo.create_session(user_id=user_id, tender_id=tender_id, title="Nuevo Hilo")

    assert older_model.is_active is False
    assert new_session.is_active is True
    assert new_session.title == "Nuevo Hilo"
    assert mock_session.commit.assert_awaited


@pytest.mark.asyncio
async def test_get_session_history_returns_mapped_entities(repo, mock_session):
    session_id = uuid4()
    user_id = uuid4()
    tender_id = uuid4()

    msg_model = TenderChatMessageModel(
        id=uuid4(),
        session_id=session_id,
        tender_id=tender_id,
        user_id=user_id,
        role="user",
        content="Pregunta sesión",
        citations=[],
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    mock_exec_result = MagicMock()
    mock_exec_result.all.return_value = [msg_model]
    mock_session.exec.return_value = mock_exec_result

    history = await repo.get_session_history(session_id=session_id, user_id=user_id)
    assert len(history) == 1
    assert history[0].session_id == session_id
    assert history[0].content == "Pregunta sesión"


@pytest.mark.asyncio
async def test_save_message_with_discrepancies_and_warnings_persists_model(repo, mock_session):
    from app.domain.entities.tender_chat import DocumentDiscrepancy

    discrepancy = DocumentDiscrepancy(
        topic="Plazo de entrega",
        description="Inconsistencia de 30 vs 45 días",
        conflicting_sources=[
            Citation(document_name="DocA.pdf", page_or_sheet="1", quote="30 días"),
            Citation(document_name="DocB.pdf", page_or_sheet="5", quote="45 días"),
        ]
    )

    msg = TenderChatMessage(
        session_id=uuid4(),
        tender_id=uuid4(),
        user_id=uuid4(),
        role="assistant",
        content="Respuesta con discrepancia",
        citations=[Citation(document_name="DocA.pdf", quote="30 días")],
        discrepancies=[discrepancy],
        warnings=["El archivo anexo_danado.pdf no pudo ser procesado."],
        unbacked_aspects=["Presupuesto total estimado"],
        has_sufficient_info=False
    )

    saved = await repo.save_message(msg)

    assert saved.id == msg.id
    mock_session.add.assert_called_once()
    added_model = mock_session.add.call_args[0][0]
    assert isinstance(added_model, TenderChatMessageModel)
    assert len(added_model.discrepancies) == 1
    assert added_model.discrepancies[0]["topic"] == "Plazo de entrega"
    assert len(added_model.discrepancies[0]["conflicting_sources"]) == 2
    assert added_model.warnings == ["El archivo anexo_danado.pdf no pudo ser procesado."]
    assert added_model.unbacked_aspects == ["Presupuesto total estimado"]
    assert added_model.has_sufficient_info is False


@pytest.mark.asyncio
async def test_get_history_maps_discrepancies_and_unbacked_aspects(repo, mock_session):
    from app.domain.entities.tender_chat import DocumentDiscrepancy

    tender_id = uuid4()
    user_id = uuid4()

    model = TenderChatMessageModel(
        id=uuid4(),
        tender_id=tender_id,
        user_id=user_id,
        role="assistant",
        content="Respuesta persistida",
        citations=[{"document_name": "bases.pdf", "page_or_sheet": "1", "quote": "txt"}],
        discrepancies=[
            {
                "topic": "Garantía",
                "description": "5% vs 10%",
                "conflicting_sources": [
                    {"document_name": "A.pdf", "quote": "5%"},
                    {"document_name": "B.pdf", "quote": "10%"}
                ]
            }
        ],
        warnings=["Advertencia archivo corrupto"],
        unbacked_aspects=["Requisito X"],
        has_sufficient_info=False,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )

    mock_exec_result = MagicMock()
    mock_exec_result.all.return_value = [model]
    mock_session.exec.return_value = mock_exec_result

    history = await repo.get_history(user_id=user_id, tender_id=tender_id, limit=10)

    assert len(history) == 1
    msg = history[0]
    assert len(msg.discrepancies) == 1
    assert isinstance(msg.discrepancies[0], DocumentDiscrepancy)
    assert msg.discrepancies[0].topic == "Garantía"
    assert msg.warnings == ["Advertencia archivo corrupto"]
    assert msg.unbacked_aspects == ["Requisito X"]
    assert msg.has_sufficient_info is False


