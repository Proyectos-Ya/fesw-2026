"""Caso de uso: Arrendamiento de tareas en cola distribuida."""

from datetime import timedelta
from uuid import UUID

from app.application.repositories.extension_repository import (
    IExtensionFetchJobRepository,
    IExtensionInstallationRepository,
)
from app.application.schemas.extension_schema import ExtensionJobLeaseResponse
from app.domain.errors.extension_errors import ExtensionInstallationNotFound
from app.shared.datetime_utils import utc_now_naive


class LeaseFetchJobsUseCase:
    """Asigna la siguiente tarea de extracción comunitaria a un navegador disponible."""

    def __init__(
        self,
        installation_repo: IExtensionInstallationRepository,
        job_repo: IExtensionFetchJobRepository,
        max_daily_fetches: int = 50,
        lease_duration_seconds: int = 300,
    ) -> None:
        self.installation_repo = installation_repo
        self.job_repo = job_repo
        self.max_daily_fetches = max_daily_fetches
        self.lease_duration_seconds = lease_duration_seconds

    async def execute(self, installation_id: UUID) -> ExtensionJobLeaseResponse | None:
        inst = await self.installation_repo.get_by_id(installation_id)
        if not inst or not inst.is_active:
            raise ExtensionInstallationNotFound()

        now = utc_now_naive()
        day_ago = now - timedelta(hours=24)
        recent_count = await self.job_repo.count_recent_jobs_by_installation(
            installation_id, since=day_ago
        )
        if recent_count >= self.max_daily_fetches:
            return None

        job = await self.job_repo.lease_next_job(
            installation_id, lease_duration_seconds=self.lease_duration_seconds
        )
        if not job or not job.lease_expires_at:
            return None

        return ExtensionJobLeaseResponse(
            job_id=job.id,
            tender_id=job.tender_id,
            tender_code=job.tender_code,
            lease_expires_at=job.lease_expires_at,
        )
