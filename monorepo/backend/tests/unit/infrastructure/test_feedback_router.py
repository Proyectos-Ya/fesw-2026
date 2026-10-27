from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.domain.entities.feedback import MatchReport, MatchReportKind
from app.domain.entities.supplier_member import MemberRole, WorkspaceContext
from app.domain.entities.user import User
from app.domain.errors.supplier_errors import SupplierNotFoundForUser
from app.domain.errors.tender_errors import TenderNotFound
from app.infrastructure.routers.feedback import create_feedback_router


class _UseCase:
    def __init__(self) -> None:
        self.error: Exception | None = None
        self.calls: list[dict] = []

    async def execute(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return MatchReport(
            supplier_id=uuid4(),
            user_id=kwargs["user_id"],
            tender_id=kwargs["tender_id"],
            kind=kwargs["kind"],
            reason=kwargs["reason"],
        )


@pytest.fixture
def user() -> User:
    return User(
        id=uuid4(),
        email="test@empresa.cl",
        full_name="Usuario Prueba",
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )


@pytest.fixture
def report_use_case() -> _UseCase:
    return _UseCase()


@pytest.fixture
def active_supplier():
    return uuid4()


@pytest.fixture
def client(user, report_use_case, active_supplier) -> AsyncClient:
    app = FastAPI()
    app.include_router(
        create_feedback_router(
            get_current_user=lambda: user,
            get_report_match_use_case=lambda: report_use_case,
            get_current_workspace_context=lambda: WorkspaceContext(
                user_id=user.id,
                active_supplier_id=active_supplier,
                active_supplier_name="Empresa SpA",
                role=MemberRole.ADMIN,
            ),
        )
    )
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_reportar_un_match_responde_201_y_usa_la_empresa_activa(
    client, report_use_case, user, active_supplier
):
    tender_id = uuid4()
    response = await client.post(
        f"/tenders/{tender_id}/reports",
        json={"kind": "match", "reason": "No es mi rubro"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["tender_id"] == str(tender_id)
    assert body["kind"] == "match"
    assert body["reason"] == "No es mi rubro"
    call = report_use_case.calls[0]
    assert call["user_id"] == user.id
    assert call["supplier_id"] == active_supplier
    assert call["kind"] == MatchReportKind.MATCH


@pytest.mark.asyncio
async def test_reportar_un_analisis_es_el_mismo_endpoint_con_otro_tipo(client):
    response = await client.post(
        f"/tenders/{uuid4()}/reports",
        json={"kind": "analysis", "reason": "El puntaje no cuadra"},
    )
    assert response.status_code == 201
    assert response.json()["kind"] == "analysis"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "match", "reason": "   "},
        {"kind": "match", "reason": ""},
        {"kind": "match", "reason": "x" * 1001},
        {"kind": "otro", "reason": "algo"},
        {"reason": "falta el tipo"},
    ],
)
async def test_un_reporte_invalido_responde_422_y_no_llega_al_caso_de_uso(
    client, report_use_case, payload
):
    response = await client.post(f"/tenders/{uuid4()}/reports", json=payload)
    assert response.status_code == 422
    assert report_use_case.calls == []


@pytest.mark.asyncio
async def test_licitacion_inexistente_responde_404(client, report_use_case):
    report_use_case.error = TenderNotFound(uuid4())
    response = await client.post(
        f"/tenders/{uuid4()}/reports", json={"kind": "match", "reason": "x"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_usuario_sin_empresa_responde_404(client, report_use_case, user):
    report_use_case.error = SupplierNotFoundForUser(user.id)
    response = await client.post(
        f"/tenders/{uuid4()}/reports", json={"kind": "match", "reason": "x"}
    )
    assert response.status_code == 404
