"""Pruebas del router de digest de licitaciones (plan 233, decisión 4)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.use_cases.attachment_processing.get_tender_digest import (
    GetTenderDigestUseCase,
    TenderDigestView,
)
from app.domain.entities.supplier_member import WorkspaceContext
from app.domain.entities.tender_digest import (
    TenderDigest,
    TenderDigestData,
)
from app.domain.errors.tender_errors import TenderNotFound
from app.infrastructure.routers.tender_digest import create_tender_digest_router

TENDER_ID = uuid4()
WS_ID = uuid4()


@pytest.fixture
def use_case_mock() -> AsyncMock:
    return AsyncMock(spec=GetTenderDigestUseCase)


@pytest.fixture
def app_and_client(use_case_mock: AsyncMock):
    app = FastAPI()

    def get_user():
        return {"id": "u-1"}

    def get_ws():
        return WorkspaceContext(
            user_id=uuid4(),
            active_supplier_id=WS_ID,
            active_supplier_name="Empresa Test",
            role="admin",
            permissions=["view"],
        )

    router = create_tender_digest_router(
        get_user,
        lambda: use_case_mock,
        get_optional_workspace_context=get_ws,
    )
    app.include_router(router)
    return app, TestClient(app)


def test_200_con_digest_vigente(app_and_client, use_case_mock: AsyncMock):
    app, client = app_and_client
    data = TenderDigestData.vacio()
    digest = TenderDigest(
        id=uuid4(),
        tender_id=TENDER_ID,
        workspace_id=WS_ID,
        version=1,
        extraction_set_hash="hash123",
        is_current=True,
        source_count=2,
        data=data,
        api_snapshot={},
        created_at=datetime(2026, 10, 4, 12, 0, tzinfo=UTC),
    )
    use_case_mock.execute.return_value = TenderDigestView(
        tender_id=TENDER_ID,
        digest=digest,
        scope="workspace",
        pending_sources=1,
    )

    resp = client.get(f"/tenders/{TENDER_ID}/digest")
    assert resp.status_code == 200
    cuerpo = resp.json()
    esperadas = {
        "tender_id",
        "status",
        "scope",
        "version",
        "generated_at",
        "pending_sources",
        "ai_generated",
        "campos",
        "requisitos",
        "items",
        "entregables",
        "puntos_a_tener_en_cuenta",
        "resumenes",
        "otras_citas",
        "discrepancias",
        "fuentes",
    }
    assert set(cuerpo.keys()) == esperadas
    assert cuerpo["status"] == "ready"
    assert cuerpo["version"] == 1
    assert cuerpo["scope"] == "workspace"
    assert cuerpo["ai_generated"] is True
    assert cuerpo["generated_at"].endswith("Z")
    use_case_mock.execute.assert_awaited_once_with(TENDER_ID, workspace_id=WS_ID)


def test_vista_vacia_devuelve_empty(app_and_client, use_case_mock: AsyncMock):
    app, client = app_and_client
    use_case_mock.execute.return_value = TenderDigestView(
        tender_id=TENDER_ID,
        digest=None,
        scope="shared",
        pending_sources=0,
    )

    resp = client.get(f"/tenders/{TENDER_ID}/digest")
    assert resp.status_code == 200
    cuerpo = resp.json()
    assert cuerpo["status"] == "empty"
    assert cuerpo["version"] is None
    assert cuerpo["generated_at"] is None
    assert cuerpo["requisitos"] == []
    assert cuerpo["discrepancias"] == []


def test_tender_not_found_da_404(app_and_client, use_case_mock: AsyncMock):
    app, client = app_and_client
    use_case_mock.execute.side_effect = TenderNotFound(TENDER_ID)

    resp = client.get(f"/tenders/{TENDER_ID}/digest")
    assert resp.status_code == 404
    assert str(TENDER_ID) in resp.json()["detail"]


def test_openapi_summary_y_tags(app_and_client):
    app, _ = app_and_client
    schema = app.openapi()
    ruta = schema["paths"]["/tenders/{tender_id}/digest"]["get"]
    assert ruta["summary"] == "Ver el resumen de los anexos de una licitación"
    assert ruta["tags"] == ["Tender attachments"]
