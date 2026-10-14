"""Caso de uso: Reporte de resultado de ejecución de tareas."""

from uuid import UUID

from app.application.repositories.extension_repository import (
    IExtensionFetchJobRepository,
)
from app.application.schemas.extension_schema import (
    ExtensionJobResultRequest,
    ExtensionJobResultResponse,
)
from app.domain.errors.extension_errors import ExtensionJobNotFound


class ReportJobResultUseCase:
    """Registra el término exitoso o fallo de una tarea de extracción."""

    def __init__(self, job_repo: IExtensionFetchJobRepository) -> None:
        self.job_repo = job_repo

    async def execute(
        self, job_id: UUID, request: ExtensionJobResultRequest
    ) -> ExtensionJobResultResponse:
        if request.status == "completed":
            job = await self.job_repo.complete_job(
                job_id, result_summary=request.result_summary
            )
        else:
            job = await self.job_repo.fail_job(
                job_id,
                error_code=request.error_code,
                error_detail=request.error_detail,
            )

        if not job:
            raise ExtensionJobNotFound()

        return ExtensionJobResultResponse(
            job_id=job.id,
            status=job.status,
            acknowledged=True,
        )
