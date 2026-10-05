"""Pruebas unitarias para el router de la extensión (Plan 233, Decisión 7)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from app.application.schemas.extension_schema import (
    ExtensionCapabilitiesResponse,
    ExtensionJobLeaseResponse,
    ExtensionPairingConfirmResponse,
    ExtensionPairingStartResponse,
)
from app.domain.entities.extension_installation import ExtensionInstallation
from app.domain.entities.user import User
from app.domain.errors.extension_errors import (
    ExtensionInstallationNotFound,
    InvalidPairingTicketError,
    PairingTicketExpiredError,
)
from app.infrastructure.routers.extension import create_extension_router


@pytest.fixture
def dummy_user():
    return User(
        id=uuid4(),
        email="test@chiripa.cl",
        rut="12345678-5",
        full_name="Usuario Test",
    )


@pytest.fixture
def mock_capabilities_use_case():
    mock = MagicMock()
    mock.execute.return_value = ExtensionCapabilitiesResponse(
        enabled=True,
        min_version="0.1.0",
        latest_version="0.1.0",
        mp_adapter_enabled=True,
        fetch_jobs_enabled=True,
        max_daily_fetches=50,
    )
    return mock


@pytest.fixture
def mock_pair_use_case():
    mock = MagicMock()
    mock.confirm_pairing = AsyncMock()
    return mock


@pytest.fixture
def mock_check_attachments_use_case():
    return AsyncMock()


@pytest.fixture
def mock_lease_jobs_use_case():
    return AsyncMock()


@pytest.fixture
def mock_report_job_result_use_case():
    return AsyncMock()


@pytest.fixture
def mock_installation_repo():
    return AsyncMock()


@pytest.fixture
def client(
    dummy_user,
    mock_capabilities_use_case,
    mock_pair_use_case,
    mock_check_attachments_use_case,
    mock_lease_jobs_use_case,
    mock_report_job_result_use_case,
    mock_installation_repo,
):
    app = FastAPI()
    router = create_extension_router(
        capabilities_use_case=mock_capabilities_use_case,
        pair_extension_use_case=mock_pair_use_case,
        check_attachments_use_case=mock_check_attachments_use_case,
        lease_jobs_use_case=mock_lease_jobs_use_case,
        report_job_result_use_case=mock_report_job_result_use_case,
        installation_repo=mock_installation_repo,
        get_current_user=lambda: dummy_user,
        get_optional_workspace_context=lambda: None,
    )
    app.include_router(router)
    return TestClient(app)


def test_get_capabilities_publico(client, mock_capabilities_use_case):
    res = client.get("/extension/capabilities")
    assert res.status_code == 200
    data = res.json()
    assert data["enabled"] is True
    assert data["max_daily_fetches"] == 50


def test_pairing_start(client, mock_pair_use_case):
    mock_pair_use_case.start_pairing.return_value = ExtensionPairingStartResponse(
        pairing_ticket="TKT-ABC123",
        expires_in_seconds=300,
    )
    res = client.post(
        "/extension/pairing/start",
        json={"browser": "chrome", "extension_version": "0.1.0"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["pairing_ticket"] == "TKT-ABC123"


def test_pairing_confirm_exitoso(client, mock_pair_use_case, mock_capabilities_use_case):
    inst_id = uuid4()
    mock_pair_use_case.confirm_pairing.return_value = ExtensionPairingConfirmResponse(
        installation_id=inst_id,
        status="paired",
        workspace_id=None,
        capabilities=mock_capabilities_use_case.execute(),
    )

    res = client.post(
        "/extension/pairing/confirm",
        json={
            "pairing_ticket": "TKT-ABC123",
            "installation_id": str(inst_id),
            "browser": "chrome",
            "extension_version": "0.1.0",
        },
    )
    assert res.status_code == 200
    assert res.json()["status"] == "paired"


def test_pairing_confirm_ticket_invalido(client, mock_pair_use_case):
    mock_pair_use_case.confirm_pairing.side_effect = InvalidPairingTicketError()

    res = client.post(
        "/extension/pairing/confirm",
        json={
            "pairing_ticket": "TKT-MALO",
            "installation_id": str(uuid4()),
            "browser": "chrome",
            "extension_version": "0.1.0",
        },
    )
    assert res.status_code == 400
    assert "ticket" in res.json()["detail"].lower()


def test_jobs_lease_retorna_204_si_vacio(client, mock_lease_jobs_use_case):
    mock_lease_jobs_use_case.execute.return_value = None

    res = client.post(
        "/extension/jobs/lease",
        json={"installation_id": str(uuid4())},
    )
    assert res.status_code == 204


def test_jobs_lease_retorna_job(client, mock_lease_jobs_use_case):
    job_id = uuid4()
    tender_id = uuid4()
    now = datetime.now(UTC).replace(tzinfo=None)
    mock_lease_jobs_use_case.execute.return_value = ExtensionJobLeaseResponse(
        job_id=job_id,
        tender_id=tender_id,
        tender_code="10-1-COT",
        lease_expires_at=now,
    )

    res = client.post(
        "/extension/jobs/lease",
        json={"installation_id": str(uuid4())},
    )
    assert res.status_code == 200
    assert res.json()["tender_code"] == "10-1-COT"
