"""Implementación SQLModel/PostgreSQL de los repositorios de la extensión (Plan 233, Decisión 7)."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.extension_repository import (
    IExtensionFetchJobRepository,
    IExtensionInstallationRepository,
)
from app.domain.entities.extension_fetch_job import ExtensionFetchJob, JobStatus
from app.domain.entities.extension_installation import (
    BrowserType,
    ExtensionInstallation,
)
from app.infrastructure.repositories.extension_model import (
    ExtensionFetchJobModel,
    ExtensionInstallationModel,
)
from app.shared.datetime_utils import utc_now_naive


def _installation_to_entity(m: ExtensionInstallationModel) -> ExtensionInstallation:
    return ExtensionInstallation(
        id=m.id,
        user_id=m.user_id,
        workspace_id=m.workspace_id,
        browser=m.browser,  # type: ignore[arg-type]
        browser_version=m.browser_version,
        extension_version=m.extension_version,
        is_active=m.is_active,
        last_heartbeat_at=m.last_heartbeat_at,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _job_to_entity(m: ExtensionFetchJobModel) -> ExtensionFetchJob:
    return ExtensionFetchJob(
        id=m.id,
        tender_id=m.tender_id,
        tender_code=m.tender_code,
        status=m.status,  # type: ignore[arg-type]
        priority=m.priority,
        leased_to_installation_id=m.leased_to_installation_id,
        leased_at=m.leased_at,
        lease_expires_at=m.lease_expires_at,
        attempts=m.attempts,
        max_attempts=m.max_attempts,
        error_code=m.error_code,
        error_detail=m.error_detail,
        result_summary=m.result_summary,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


class SqlExtensionInstallationRepository(IExtensionInstallationRepository):
    """Repositorio PostgreSQL para instalaciones de la extensión."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, installation_id: UUID) -> ExtensionInstallation | None:
        m = await self.session.get(ExtensionInstallationModel, installation_id)
        if not m:
            return None
        return _installation_to_entity(m)

    async def get_by_user_and_browser(
        self, user_id: UUID, browser: str
    ) -> ExtensionInstallation | None:
        stmt = (
            select(ExtensionInstallationModel)
            .where(
                ExtensionInstallationModel.user_id == user_id,
                ExtensionInstallationModel.browser == browser,
                ExtensionInstallationModel.is_active == True,  # noqa: E712
            )
            .order_by(col(ExtensionInstallationModel.updated_at).desc())
            .limit(1)
        )
        res = await self.session.exec(stmt)
        m = res.first()
        if not m:
            return None
        return _installation_to_entity(m)

    async def save(self, installation: ExtensionInstallation) -> ExtensionInstallation:
        m = await self.session.get(ExtensionInstallationModel, installation.id)
        now = utc_now_naive()
        if m:
            m.workspace_id = installation.workspace_id
            m.browser = str(installation.browser)
            m.browser_version = installation.browser_version
            m.extension_version = installation.extension_version
            m.is_active = installation.is_active
            m.last_heartbeat_at = installation.last_heartbeat_at
            m.updated_at = now
        else:
            m = ExtensionInstallationModel(
                id=installation.id,
                user_id=installation.user_id,
                workspace_id=installation.workspace_id,
                browser=str(installation.browser),
                browser_version=installation.browser_version,
                extension_version=installation.extension_version,
                is_active=installation.is_active,
                last_heartbeat_at=installation.last_heartbeat_at,
                created_at=installation.created_at,
                updated_at=installation.updated_at,
            )
            self.session.add(m)
        await self.session.flush()
        return _installation_to_entity(m)

    async def update_heartbeat(
        self, installation_id: UUID, heartbeat_at: datetime
    ) -> bool:
        m = await self.session.get(ExtensionInstallationModel, installation_id)
        if not m:
            return False
        m.last_heartbeat_at = heartbeat_at
        m.updated_at = heartbeat_at
        m.is_active = True
        await self.session.flush()
        return True

    async def deactivate(self, installation_id: UUID) -> bool:
        m = await self.session.get(ExtensionInstallationModel, installation_id)
        if not m:
            return False
        m.is_active = False
        m.updated_at = utc_now_naive()
        await self.session.flush()
        return True


class SqlExtensionFetchJobRepository(IExtensionFetchJobRepository):
    """Repositorio PostgreSQL para la cola distribuida de extracción."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_job(self, job: ExtensionFetchJob) -> ExtensionFetchJob:
        stmt = select(ExtensionFetchJobModel).where(
            ExtensionFetchJobModel.tender_id == job.tender_id,
            ExtensionFetchJobModel.status.in_(["pending", "leased"]),  # type: ignore[attr-defined]
        )
        res = await self.session.exec(stmt)
        existing = res.first()
        if existing:
            return _job_to_entity(existing)

        m = ExtensionFetchJobModel(
            id=job.id,
            tender_id=job.tender_id,
            tender_code=job.tender_code,
            status=job.status,
            priority=job.priority,
            leased_to_installation_id=job.leased_to_installation_id,
            leased_at=job.leased_at,
            lease_expires_at=job.lease_expires_at,
            attempts=job.attempts,
            max_attempts=job.max_attempts,
            error_code=job.error_code,
            error_detail=job.error_detail,
            result_summary=job.result_summary,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
        self.session.add(m)
        await self.session.flush()
        return _job_to_entity(m)

    async def get_by_id(self, job_id: UUID) -> ExtensionFetchJob | None:
        m = await self.session.get(ExtensionFetchJobModel, job_id)
        if not m:
            return None
        return _job_to_entity(m)

    async def get_by_tender_id(self, tender_id: UUID) -> ExtensionFetchJob | None:
        stmt = (
            select(ExtensionFetchJobModel)
            .where(ExtensionFetchJobModel.tender_id == tender_id)
            .order_by(col(ExtensionFetchJobModel.created_at).desc())
            .limit(1)
        )
        res = await self.session.exec(stmt)
        m = res.first()
        if not m:
            return None
        return _job_to_entity(m)

    async def lease_next_job(
        self, installation_id: UUID, lease_duration_seconds: int = 300
    ) -> ExtensionFetchJob | None:
        now = utc_now_naive()
        stmt = (
            select(ExtensionFetchJobModel)
            .where(
                or_(
                    ExtensionFetchJobModel.status == "pending",
                    and_(
                        ExtensionFetchJobModel.status == "leased",
                        ExtensionFetchJobModel.lease_expires_at < now,
                    ),
                )
            )
            .order_by(
                col(ExtensionFetchJobModel.priority).desc(),
                col(ExtensionFetchJobModel.created_at).asc(),
            )
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        res = await self.session.exec(stmt)
        m = res.first()
        if not m:
            return None

        m.status = "leased"
        m.leased_to_installation_id = installation_id
        m.leased_at = now
        m.lease_expires_at = now + timedelta(seconds=lease_duration_seconds)
        m.attempts += 1
        m.updated_at = now
        await self.session.flush()
        return _job_to_entity(m)

    async def complete_job(
        self, job_id: UUID, result_summary: dict[str, Any] | None = None
    ) -> ExtensionFetchJob | None:
        m = await self.session.get(ExtensionFetchJobModel, job_id)
        if not m:
            return None
        now = utc_now_naive()
        m.status = "completed"
        m.result_summary = result_summary
        m.updated_at = now
        await self.session.flush()
        return _job_to_entity(m)

    async def fail_job(
        self,
        job_id: UUID,
        error_code: str | None = None,
        error_detail: str | None = None,
    ) -> ExtensionFetchJob | None:
        m = await self.session.get(ExtensionFetchJobModel, job_id)
        if not m:
            return None
        now = utc_now_naive()
        m.error_code = error_code
        m.error_detail = error_detail
        if m.attempts >= m.max_attempts:
            m.status = "failed"
        else:
            m.status = "pending"
            m.leased_to_installation_id = None
            m.lease_expires_at = None
        m.updated_at = now
        await self.session.flush()
        return _job_to_entity(m)

    async def count_recent_jobs_by_installation(
        self, installation_id: UUID, since: datetime
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(ExtensionFetchJobModel)
            .where(
                ExtensionFetchJobModel.leased_to_installation_id == installation_id,
                ExtensionFetchJobModel.status == "completed",
                ExtensionFetchJobModel.updated_at >= since,
            )
        )
        res = await self.session.exec(stmt)
        count = res.first()
        return int(count or 0)
