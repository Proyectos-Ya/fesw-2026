"""Pruebas unitarias de entidades y esquemas de la extensión (Plan 233, Decisión 7)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.application.schemas.extension_schema import (
    DocumentCheckItem,
    ExtensionAttachmentCheckRequest,
    ExtensionAttachmentCheckResponse,
    ExtensionCapabilitiesResponse,
    ExtensionHeartbeatRequest,
    ExtensionHeartbeatResponse,
    ExtensionJobLeaseRequest,
    ExtensionJobLeaseResponse,
    ExtensionJobResultRequest,
    ExtensionJobResultResponse,
    ExtensionPairingConfirmRequest,
    ExtensionPairingConfirmResponse,
    ExtensionPairingStartRequest,
    ExtensionPairingStartResponse,
)
from app.domain.entities.extension_fetch_job import ExtensionFetchJob
from app.domain.entities.extension_installation import ExtensionInstallation


def test_crear_extension_installation_valida():
    user_id = uuid4()
    ws_id = uuid4()
    inst = ExtensionInstallation(
        user_id=user_id,
        workspace_id=ws_id,
        browser="chrome",
        browser_version="130.0",
        extension_version="0.1.0",
    )
    assert inst.user_id == user_id
    assert inst.workspace_id == ws_id
    assert inst.browser == "chrome"
    assert inst.is_active is True
    assert inst.last_heartbeat_at is None
    assert inst.id is not None
    assert inst.created_at is not None


def test_extension_installation_browser_invalido():
    with pytest.raises(ValidationError):
        ExtensionInstallation(
            user_id=uuid4(),
            browser="internet_explorer",  # type: ignore[arg-type]
            extension_version="0.1.0",
        )


def test_crear_extension_fetch_job_por_defecto():
    tender_id = uuid4()
    job = ExtensionFetchJob(
        tender_id=tender_id,
        tender_code="1234-5-COT26",
    )
    assert job.tender_id == tender_id
    assert job.tender_code == "1234-5-COT26"
    assert job.status == "pending"
    assert job.priority == 0
    assert job.attempts == 0
    assert job.max_attempts == 3
    assert job.leased_to_installation_id is None
    assert job.result_summary is None


def test_schemas_capabilities():
    cap = ExtensionCapabilitiesResponse(
        enabled=True,
        min_version="0.1.0",
        latest_version="0.1.0",
        mp_adapter_enabled=True,
        fetch_jobs_enabled=True,
        max_daily_fetches=50,
    )
    assert cap.enabled is True
    assert cap.postulation_enabled is False
    assert "buscador.mercadopublico.cl" in cap.supported_mp_hosts


def test_schemas_pairing():
    start_req = ExtensionPairingStartRequest(browser="firefox", extension_version="0.1.0")
    assert start_req.browser == "firefox"

    start_resp = ExtensionPairingStartResponse(pairing_ticket="TKT-1234", expires_in_seconds=300)
    assert start_resp.pairing_ticket == "TKT-1234"

    inst_id = uuid4()
    confirm_req = ExtensionPairingConfirmRequest(
        pairing_ticket="TKT-1234",
        installation_id=inst_id,
        browser="firefox",
        extension_version="0.1.0",
    )
    assert confirm_req.installation_id == inst_id

    confirm_resp = ExtensionPairingConfirmResponse(
        installation_id=inst_id,
        status="paired",
        workspace_id=None,
        capabilities=ExtensionCapabilitiesResponse(enabled=True),
    )
    assert confirm_resp.status == "paired"


def test_schemas_attachment_check():
    req = ExtensionAttachmentCheckRequest(
        tender_code="2026-10-COT",
        documents=[DocumentCheckItem(mp_document_id="101", name="Bases.pdf")],
    )
    assert req.tender_code == "2026-10-COT"
    assert len(req.documents) == 1

    resp = ExtensionAttachmentCheckResponse(
        tender_id=uuid4(),
        tender_code="2026-10-COT",
        documents=[],
    )
    assert resp.tender_code == "2026-10-COT"


def test_schemas_jobs():
    inst_id = uuid4()
    lease_req = ExtensionJobLeaseRequest(installation_id=inst_id)
    assert lease_req.installation_id == inst_id

    now = datetime.now(UTC).replace(tzinfo=None)
    lease_resp = ExtensionJobLeaseResponse(
        job_id=uuid4(),
        tender_id=uuid4(),
        tender_code="10-2-COT",
        lease_expires_at=now,
    )
    assert lease_resp.tender_code == "10-2-COT"

    result_req = ExtensionJobResultRequest(
        installation_id=inst_id,
        status="completed",
        result_summary={"attachments_uploaded": 2},
    )
    assert result_req.status == "completed"

    result_resp = ExtensionJobResultResponse(
        job_id=uuid4(),
        status="completed",
        acknowledged=True,
    )
    assert result_resp.acknowledged is True
