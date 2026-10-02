from datetime import datetime
from uuid import UUID

from sqlalchemy import update
from sqlmodel import col
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.export_job_repository import IExportJobRepository
from app.domain.entities.export_job import (
    ExportFormat,
    ExportJob,
    ExportJobStatus,
)
from app.infrastructure.repositories.export_job_model import ExportJobModel

_REINICIO = "La API se reinició durante la generación."


class ExportJobRepository(IExportJobRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_entity(model: ExportJobModel) -> ExportJob:
        return ExportJob(
            id=model.id,
            user_id=model.user_id,
            supplier_id=model.supplier_id,
            tender_id=model.tender_id,
            format=ExportFormat(model.format),
            sections=list(model.sections),
            status=ExportJobStatus(model.status),
            file_name=model.file_name,
            content=model.content,
            error=model.error,
            created_at=model.created_at,
            finished_at=model.finished_at,
            expires_at=model.expires_at,
        )

    async def save(self, job: ExportJob) -> ExportJob:
        datos = job.model_dump()
        datos["format"] = job.format.value
        datos["status"] = job.status.value
        try:
            await self.session.merge(ExportJobModel(**datos))
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return job

    async def get(self, job_id: UUID) -> ExportJob | None:
        model = await self.session.get(ExportJobModel, job_id)
        return self._to_entity(model) if model is not None else None

    async def _update(self, statement) -> int:
        try:
            result = await self.session.exec(statement)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return result.rowcount or 0

    async def fail_stale(self, now: datetime) -> int:
        return await self._update(
            update(ExportJobModel)
            .where(col(ExportJobModel.status) == ExportJobStatus.PROCESSING.value)
            .values(status=ExportJobStatus.FAILED.value, error=_REINICIO, finished_at=now)
        )

    async def purge_expired(self, now: datetime) -> int:
        return await self._update(
            update(ExportJobModel)
            .where(
                col(ExportJobModel.content).is_not(None),
                col(ExportJobModel.expires_at) <= now,
            )
            .values(content=None)
        )
