from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient

from app.application.use_cases.upload_tender_chat_document_use_case import (
    UploadTenderChatDocumentResult,
)
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.quotation import MaterialItem, Quotation
from app.domain.entities.supplier_member import WorkspaceContext
from app.domain.entities.tender_chat import TenderChatDocument
from app.domain.entities.user import User
from app.infrastructure.routers.tender_chat import create_tender_chat_router
from app.shared.datetime_utils import utc_now_naive


@pytest.fixture
def test_user():
    return User(
        id=uuid4(),
        email="test@empresa.cl",
        hashed_password="hash",
        full_name="Usuario Test",
        active=True,
        created_at=datetime.now(UTC).replace(tzinfo=None),
        updated_at=datetime.now(UTC).replace(tzinfo=None),
    )


@pytest.fixture
def mock_upload_use_case():
    return AsyncMock()


@pytest.fixture
def app_with_router(test_user, mock_upload_use_case):
    app = FastAPI()

    supplier_id = uuid4()
    workspace_ctx = WorkspaceContext(
        user_id=test_user.id,
        active_supplier_id=supplier_id,
        active_supplier_name="Empresa Test SpA",
        role="admin",
    )

    router = create_tender_chat_router(
        get_current_user=lambda: test_user,
        get_upload_doc_use_case=lambda: mock_upload_use_case,
        get_list_docs_use_case=lambda: None,
        get_delete_doc_use_case=lambda: None,
        get_ask_assistant_use_case=lambda: None,
        get_chat_history_use_case=lambda: None,
        get_create_chat_session_use_case=lambda: None,
        get_current_workspace_context=lambda: workspace_ctx,
    )
    app.include_router(router)
    return app, supplier_id


@pytest.mark.asyncio
async def test_upload_endpoint_returns_deep_analysis_and_quotation(
    app_with_router, test_user, mock_upload_use_case
):
    app, expected_supplier_id = app_with_router
    tender_id = uuid4()
    doc_id = uuid4()

    mock_analysis = DeepAnalysis(
        id=uuid4(),
        tender_id=tender_id,
        supplier_id=expected_supplier_id,
        compatibility_score=87.5,
        recommendation="Postular",
        justification="Cumplimiento exhaustivo de bases técnicas.",
    )
    mock_quotation = Quotation(
        id=uuid4(),
        supplier_id=expected_supplier_id,
        tender_id=tender_id,
        currency="CLP",
        updated_at=utc_now_naive(),
        items=[
            MaterialItem(
                description="Cable Cobre",
                unit="rollo",
                quantity=Decimal("10"),
                unit_price=Decimal("50000"),
            )
        ],
    )

    enriched_result = UploadTenderChatDocumentResult(
        id=doc_id,
        tender_id=tender_id,
        user_id=test_user.id,
        file_name="especificaciones.pdf",
        file_type="pdf",
        file_size_bytes=1024,
        storage_path=f"uploads/{tender_id}/especificaciones.pdf",
        deep_analysis=mock_analysis,
        quotation=mock_quotation,
    )
    mock_upload_use_case.execute = AsyncMock(return_value=enriched_result)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        files = {"file": ("especificaciones.pdf", b"%PDF-1.4 sample", "application/pdf")}
        response = await client.post(f"/tenders/{tender_id}/assistant/documents", files=files)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()

    # Campos de documento
    assert data["id"] == str(doc_id)
    assert data["file_name"] == "especificaciones.pdf"
    assert data["file_type"] == "pdf"

    # Campos enriquecidos
    assert data["deep_analysis"] is not None
    assert data["deep_analysis"]["compatibility_score"] == 87.5
    assert data["deep_analysis"]["recommendation"] == "Postular"
    assert "Cumplimiento exhaustivo" in data["deep_analysis"]["justification"]
    assert data["deep_analysis"]["is_outdated"] is False

    assert data["quotation"] is not None
    assert data["quotation"]["currency"] == "CLP"
    assert len(data["quotation"]["items"]) == 1
    assert data["quotation"]["items"][0]["description"] == "Cable Cobre"
    assert float(data["quotation"]["total"]) == 500000.0

    # Verifica que supplier_id del workspace context fue propagado al caso de uso
    mock_upload_use_case.execute.assert_called_once()
    call_kwargs = mock_upload_use_case.execute.call_args.kwargs
    assert call_kwargs["supplier_id"] == expected_supplier_id


@pytest.mark.asyncio
async def test_upload_endpoint_backwards_compatible_when_no_analysis(
    app_with_router, test_user, mock_upload_use_case
):
    """Verifica compatibilidad cuando el caso de uso devuelve documento simple sin análisis ni cotización."""
    app, _ = app_with_router
    tender_id = uuid4()
    doc_id = uuid4()

    simple_doc = TenderChatDocument(
        id=doc_id,
        tender_id=tender_id,
        user_id=test_user.id,
        file_name="plano.png",
        file_type="png",
        file_size_bytes=512,
        storage_path=f"uploads/{tender_id}/plano.png",
    )
    mock_upload_use_case.execute = AsyncMock(return_value=simple_doc)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        files = {"file": ("plano.png", b"fake-png", "image/png")}
        response = await client.post(f"/tenders/{tender_id}/assistant/documents", files=files)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["id"] == str(doc_id)
    assert data["file_name"] == "plano.png"
    assert data["deep_analysis"] is None
    assert data["quotation"] is None
