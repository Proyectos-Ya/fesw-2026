"""Pruebas unitarias de los repositorios SQL de extensión (Plan 233, Decisión 7)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.domain.entities.extension_fetch_job import ExtensionFetchJob
from app.domain.entities.extension_installation import ExtensionInstallation
from app.infrastructure.repositories.extension_model import (
    ExtensionFetchJobModel,
    ExtensionInstallationModel,
)
from app.infrastructure.repositories.sql_extension_repository import (
    SqlExtensionFetchJobRepository,
    SqlExtensionInstallationRepository,
)


@pytest.fixture
def mock_session():
    session = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_save_new_installation(mock_session):
    repo = SqlExtensionInstallationRepository(mock_session)
    mock_session.get.return_value = None

    inst = ExtensionInstallation(
        id=uuid4(),
        user_id=uuid4(),
        browser="chrome",
        browser_version="130.0",
        extension_version="0.1.0",
    )

    saved = await repo.save(inst)

    assert saved.id == inst.id
    assert saved.browser == "chrome"
    mock_session.add.assert_called_once()
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_existing_installation(mock_session):
    repo = SqlExtensionInstallationRepository(mock_session)
    inst_id = uuid4()
    user_id = uuid4()
    existing_model = ExtensionInstallationModel(
        id=inst_id,
        user_id=user_id,
        browser="chrome",
        extension_version="0.0.9",
        is_active=False,
    )
    mock_session.get.return_value = existing_model

    inst = ExtensionInstallation(
        id=inst_id,
        user_id=user_id,
        browser="chrome",
        extension_version="0.1.0",
        is_active=True,
    )

    saved = await repo.save(inst)

    assert saved.extension_version == "0.1.0"
    assert existing_model.extension_version == "0.1.0"
    assert existing_model.is_active is True
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_heartbeat(mock_session):
    repo = SqlExtensionInstallationRepository(mock_session)
    inst_id = uuid4()
    existing_model = ExtensionInstallationModel(
        id=inst_id,
        user_id=uuid4(),
        browser="firefox",
        extension_version="0.1.0",
        is_active=False,
    )
    mock_session.get.return_value = existing_model

    now = datetime.now(UTC).replace(tzinfo=None)
    success = await repo.update_heartbeat(inst_id, now)

    assert success is True
    assert existing_model.last_heartbeat_at == now
    assert existing_model.is_active is True


@pytest.mark.asyncio
async def test_deactivate_installation(mock_session):
    repo = SqlExtensionInstallationRepository(mock_session)
    inst_id = uuid4()
    existing_model = ExtensionInstallationModel(
        id=inst_id,
        user_id=uuid4(),
        browser="edge",
        extension_version="0.1.0",
        is_active=True,
    )
    mock_session.get.return_value = existing_model

    success = await repo.deactivate(inst_id)

    assert success is True
    assert existing_model.is_active is False


@pytest.mark.asyncio
async def test_create_job_idempotent(mock_session):
    repo = SqlExtensionFetchJobRepository(mock_session)
    tender_id = uuid4()

    # Simular que ya existe uno activo
    existing_model = ExtensionFetchJobModel(
        id=uuid4(),
        tender_id=tender_id,
        tender_code="100-2-COT",
        status="pending",
    )
    exec_result = MagicMock()
    exec_result.first.return_value = existing_model
    mock_session.exec.return_value = exec_result

    job = ExtensionFetchJob(
        tender_id=tender_id,
        tender_code="100-2-COT",
    )

    created = await repo.create_job(job)

    assert created.id == existing_model.id
    mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_lease_next_job(mock_session):
    repo = SqlExtensionFetchJobRepository(mock_session)
    job_id = uuid4()
    inst_id = uuid4()

    job_model = ExtensionFetchJobModel(
        id=job_id,
        tender_id=uuid4(),
        tender_code="100-2-COT",
        status="pending",
        attempts=0,
    )
    exec_result = MagicMock()
    exec_result.first.return_value = job_model
    mock_session.exec.return_value = exec_result

    leased = await repo.lease_next_job(inst_id, lease_duration_seconds=300)

    assert leased is not None
    assert leased.id == job_id
    assert job_model.status == "leased"
    assert job_model.leased_to_installation_id == inst_id
    assert job_model.attempts == 1
    assert job_model.lease_expires_at is not None
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_complete_job(mock_session):
    repo = SqlExtensionFetchJobRepository(mock_session)
    job_id = uuid4()
    job_model = ExtensionFetchJobModel(
        id=job_id,
        tender_id=uuid4(),
        tender_code="100-2-COT",
        status="leased",
    )
    mock_session.get.return_value = job_model

    completed = await repo.complete_job(job_id, result_summary={"count": 3})

    assert completed is not None
    assert completed.status == "completed"
    assert job_model.status == "completed"
    assert job_model.result_summary == {"count": 3}


@pytest.mark.asyncio
async def test_fail_job_retry_or_fail(mock_session):
    repo = SqlExtensionFetchJobRepository(mock_session)
    job_id = uuid4()
    job_model = ExtensionFetchJobModel(
        id=job_id,
        tender_id=uuid4(),
        tender_code="100-2-COT",
        status="leased",
        attempts=1,
        max_attempts=3,
    )
    mock_session.get.return_value = job_model

    # Primer intento fallido -> debe volver a pending
    retried = await repo.fail_job(job_id, error_code="timeout")
    assert retried.status == "pending"
    assert job_model.status == "pending"
    assert job_model.leased_to_installation_id is None

    # Tercer intento fallido -> debe marcarse como failed
    job_model.attempts = 3
    failed = await repo.fail_job(job_id, error_code="not_found")
    assert failed.status == "failed"
    assert job_model.status == "failed"
