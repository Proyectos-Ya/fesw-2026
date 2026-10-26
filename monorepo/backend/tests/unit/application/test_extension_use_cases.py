"""Pruebas unitarias de casos de uso de la extensión (Plan 233, Decisión 7)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.application.schemas.extension_schema import (
    DocumentCheckItem,
    ExtensionAttachmentCheckRequest,
    ExtensionJobResultRequest,
    ExtensionPairingConfirmRequest,
    ExtensionPairingStartRequest,
)
from app.application.use_cases.extension.check_extension_attachments import (
    CheckExtensionAttachmentsUseCase,
)
from app.application.use_cases.extension.get_extension_capabilities import (
    GetExtensionCapabilitiesUseCase,
)
from app.application.use_cases.extension.lease_fetch_jobs import (
    LeaseFetchJobsUseCase,
)
from app.application.use_cases.extension.pair_extension import (
    PairExtensionUseCase,
)
from app.application.use_cases.extension.report_job_result import (
    ReportJobResultUseCase,
)
from app.config import Settings
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
    AttachmentTrust,
    AttachmentVisibility,
)
from app.domain.entities.extension_fetch_job import ExtensionFetchJob
from app.domain.entities.extension_installation import ExtensionInstallation
from app.domain.entities.tender_attachment import (
    OfficialAttachment,
    OfficialAttachmentList,
)
from app.domain.errors.extension_errors import (
    ExtensionInstallationNotFound,
    InvalidPairingTicketError,
    PairingTicketExpiredError,
)


@pytest.fixture
def mock_installation_repo():
    return AsyncMock()


@pytest.fixture
def mock_job_repo():
    return AsyncMock()


@pytest.fixture
def mock_tender_attachment_repo():
    return AsyncMock()


@pytest.fixture
def mock_attachment_file_repo():
    return AsyncMock()


# --- 1. GetExtensionCapabilitiesUseCase ---

def test_capabilities_enabled():
    mock_settings = MagicMock(spec=Settings)
    mock_settings.extension_enabled = True
    mock_settings.extension_min_version = "0.1.0"
    mock_settings.extension_latest_version = "0.1.0"
    mock_settings.extension_max_daily_fetches = 50
    mock_settings.extension_polling_interval_seconds = 300

    use_case = GetExtensionCapabilitiesUseCase(settings=mock_settings)
    cap = use_case.execute()

    assert cap.enabled is True
    assert cap.fetch_jobs_enabled is True
    assert cap.max_daily_fetches == 50
    assert "buscador.mercadopublico.cl" in cap.supported_mp_hosts


def test_capabilities_disabled():
    mock_settings = MagicMock(spec=Settings)
    mock_settings.extension_enabled = False
    mock_settings.extension_min_version = "0.1.0"
    mock_settings.extension_latest_version = "0.1.0"
    mock_settings.extension_max_daily_fetches = 0
    mock_settings.extension_polling_interval_seconds = 300

    use_case = GetExtensionCapabilitiesUseCase(settings=mock_settings)
    cap = use_case.execute()

    assert cap.enabled is False
    assert cap.mp_adapter_enabled is False
    assert cap.fetch_jobs_enabled is False


# --- 2. PairExtensionUseCase ---

@pytest.mark.asyncio
async def test_pair_extension_lifecycle(mock_installation_repo):
    use_case = PairExtensionUseCase(installation_repo=mock_installation_repo)
    user_id = uuid4()
    workspace_id = uuid4()

    start_res = use_case.start_pairing(user_id=user_id, workspace_id=workspace_id)
    ticket = start_res.pairing_ticket
    assert ticket.startswith("TKT-")

    inst_id = uuid4()
    confirm_req = ExtensionPairingConfirmRequest(
        pairing_ticket=ticket,
        installation_id=inst_id,
        browser="chrome",
        browser_version="130.0",
        extension_version="0.1.0",
    )

    mock_installation_repo.get_by_id.return_value = None
    mock_installation_repo.save.side_effect = lambda inst: inst

    confirm_res = await use_case.confirm_pairing(confirm_req)

    assert confirm_res.installation_id == inst_id
    assert confirm_res.status == "paired"
    assert confirm_res.workspace_id == workspace_id
    assert confirm_res.capabilities.enabled is True
    mock_installation_repo.save.assert_called_once()

    # Reutilizar ticket -> debe fallar con InvalidPairingTicketError
    with pytest.raises(InvalidPairingTicketError):
        await use_case.confirm_pairing(confirm_req)


@pytest.mark.asyncio
async def test_pair_extension_ticket_invalido(mock_installation_repo):
    use_case = PairExtensionUseCase(installation_repo=mock_installation_repo)
    confirm_req = ExtensionPairingConfirmRequest(
        pairing_ticket="TKT-INEXISTENTE",
        installation_id=uuid4(),
        browser="chrome",
        extension_version="0.1.0",
    )
    with pytest.raises(InvalidPairingTicketError):
        await use_case.confirm_pairing(confirm_req)


# --- 3. CheckExtensionAttachmentsUseCase ---

@pytest.mark.asyncio
async def test_check_attachments_tender_inexistente(
    mock_tender_attachment_repo, mock_attachment_file_repo
):
    mock_tender_attachment_repo.get_tender_ids_by_codes.return_value = {}

    use_case = CheckExtensionAttachmentsUseCase(
        tender_attachment_repo=mock_tender_attachment_repo,
        attachment_file_repo=mock_attachment_file_repo,
    )

    req = ExtensionAttachmentCheckRequest(
        tender_code="999-9-COT",
        documents=[DocumentCheckItem(mp_document_id="101", name="Bases.pdf")],
    )

    res = await use_case.execute(req)

    assert res.tender_id is None
    assert res.tender_code == "999-9-COT"
    assert len(res.documents) == 1
    assert res.documents[0].exists is False
    assert res.documents[0].status == "missing"


@pytest.mark.asyncio
async def test_check_attachments_con_archivo_guardado(
    mock_tender_attachment_repo, mock_attachment_file_repo
):
    tender_id = uuid4()
    mock_tender_attachment_repo.get_tender_ids_by_codes.return_value = {
        "100-1-COT": tender_id
    }

    now = datetime.now(UTC).replace(tzinfo=None)
    att_id = uuid4()
    mock_tender_attachment_repo.get_official_list.return_value = OfficialAttachmentList(
        attachments=[
            OfficialAttachment(
                id=att_id,
                tender_id=tender_id,
                mp_document_id=101,
                name="Bases.pdf",
                name_normalized="bases.pdf",
                ext=".pdf",
                first_seen_at=now,
                last_seen_at=now,
            )
        ]
    )

    mock_attachment_file_repo.get_canonical_file.return_value = AttachmentFile(
        id=uuid4(),
        tender_attachment_id=att_id,
        tender_id=tender_id,
        sha256="abcdef123456",
        size_bytes=1024,
        mime_declared="application/pdf",
        storage_key="shared/tender/101/hash.pdf",
        source=AttachmentFileSource.EXTENSION,
        uploader_user_id=None,
        workspace_id=None,
        visibility=AttachmentVisibility.SHARED,
        trust=AttachmentTrust.CORROBORATED,
        status=AttachmentFileStatus.STORED,
        created_at=now,
        completed_at=now,
    )

    use_case = CheckExtensionAttachmentsUseCase(
        tender_attachment_repo=mock_tender_attachment_repo,
        attachment_file_repo=mock_attachment_file_repo,
    )

    req = ExtensionAttachmentCheckRequest(
        tender_code="100-1-COT",
        documents=[
            DocumentCheckItem(mp_document_id="101", name="Bases.pdf"),
            DocumentCheckItem(mp_document_id="102", name="Anexo1.xlsx"),
        ],
    )

    res = await use_case.execute(req)

    assert res.tender_id == tender_id
    assert len(res.documents) == 2
    doc_101 = next(d for d in res.documents if d.mp_document_id == "101")
    assert doc_101.exists is True
    assert doc_101.status == "stored"

    doc_102 = next(d for d in res.documents if d.mp_document_id == "102")
    assert doc_102.exists is False
    assert doc_102.status == "missing"


# --- 4. LeaseFetchJobsUseCase ---

@pytest.mark.asyncio
async def test_lease_job_exito(mock_installation_repo, mock_job_repo):
    inst_id = uuid4()
    inst = ExtensionInstallation(
        id=inst_id,
        user_id=uuid4(),
        browser="firefox",
        extension_version="0.1.0",
        is_active=True,
    )
    mock_installation_repo.get_by_id.return_value = inst
    mock_job_repo.count_recent_jobs_by_installation.return_value = 5

    now = datetime.now(UTC).replace(tzinfo=None)
    job_id = uuid4()
    tender_id = uuid4()
    mock_job = ExtensionFetchJob(
        id=job_id,
        tender_id=tender_id,
        tender_code="200-2-COT",
        status="leased",
        leased_to_installation_id=inst_id,
        lease_expires_at=now + timedelta(minutes=5),
    )
    mock_job_repo.lease_next_job.return_value = mock_job

    use_case = LeaseFetchJobsUseCase(
        installation_repo=mock_installation_repo,
        job_repo=mock_job_repo,
        max_daily_fetches=50,
    )

    lease_res = await use_case.execute(inst_id)

    assert lease_res is not None
    assert lease_res.job_id == job_id
    assert lease_res.tender_code == "200-2-COT"


@pytest.mark.asyncio
async def test_lease_job_cuota_excedida(mock_installation_repo, mock_job_repo):
    inst_id = uuid4()
    inst = ExtensionInstallation(
        id=inst_id,
        user_id=uuid4(),
        browser="firefox",
        extension_version="0.1.0",
        is_active=True,
    )
    mock_installation_repo.get_by_id.return_value = inst
    mock_job_repo.count_recent_jobs_by_installation.return_value = 50

    use_case = LeaseFetchJobsUseCase(
        installation_repo=mock_installation_repo,
        job_repo=mock_job_repo,
        max_daily_fetches=50,
    )

    lease_res = await use_case.execute(inst_id)
    assert lease_res is None
    mock_job_repo.lease_next_job.assert_not_called()


@pytest.mark.asyncio
async def test_lease_job_instalacion_invalida(mock_installation_repo, mock_job_repo):
    mock_installation_repo.get_by_id.return_value = None

    use_case = LeaseFetchJobsUseCase(
        installation_repo=mock_installation_repo,
        job_repo=mock_job_repo,
    )

    with pytest.raises(ExtensionInstallationNotFound):
        await use_case.execute(uuid4())


# --- 5. ReportJobResultUseCase ---

@pytest.mark.asyncio
async def test_report_job_result_completed(mock_job_repo):
    use_case = ReportJobResultUseCase(job_repo=mock_job_repo)
    job_id = uuid4()

    mock_job_repo.complete_job.return_value = ExtensionFetchJob(
        id=job_id,
        tender_id=uuid4(),
        tender_code="10-1-COT",
        status="completed",
    )

    req = ExtensionJobResultRequest(
        installation_id=uuid4(),
        status="completed",
        result_summary={"files_uploaded": 2},
    )

    res = await use_case.execute(job_id, req)

    assert res.job_id == job_id
    assert res.status == "completed"
    assert res.acknowledged is True
    mock_job_repo.complete_job.assert_awaited_once_with(
        job_id, result_summary={"files_uploaded": 2}
    )
