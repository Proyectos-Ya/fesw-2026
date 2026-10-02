"""Dobles para las exportaciones de licitaciones (HdU 19)."""

from datetime import datetime
from uuid import UUID, uuid4

from app.application.repositories.export_job_repository import IExportJobRepository
from app.domain.entities.export_job import ExportJob, ExportJobStatus
from app.domain.entities.quotation import Quotation, QuotationInput
from app.shared.datetime_utils import utc_now_naive


class InMemoryExportJobRepository(IExportJobRepository):
    def __init__(self) -> None:
        self.jobs: dict[UUID, ExportJob] = {}

    async def save(self, job: ExportJob) -> ExportJob:
        self.jobs[job.id] = job
        return job

    async def get(self, job_id: UUID, with_content: bool = True) -> ExportJob | None:
        job = self.jobs.get(job_id)
        if job is not None and not with_content:
            return job.model_copy(update={"content": None})
        return job

    async def fail_stale(self, now: datetime) -> int:
        en_proceso = [j for j in self.jobs.values() if j.status is ExportJobStatus.PROCESSING]
        for job in en_proceso:
            self.jobs[job.id] = job.fallido("La API se reinició durante la generación.", now)
        return len(en_proceso)

    async def purge_expired(self, now: datetime) -> int:
        vencidos = [j for j in self.jobs.values() if j.content is not None and now >= j.expires_at]
        for job in vencidos:
            self.jobs[job.id] = job.model_copy(update={"content": None})
        return len(vencidos)


class InMemoryQuotationRepository:
    def __init__(self) -> None:
        self.quotations: dict[tuple[UUID, UUID], Quotation] = {}

    async def get(self, supplier_id: UUID, tender_id: UUID) -> Quotation | None:
        return self.quotations.get((supplier_id, tender_id))

    async def save(self, supplier_id: UUID, tender_id: UUID, data: QuotationInput) -> Quotation:
        guardada = Quotation(
            id=uuid4(),
            supplier_id=supplier_id,
            tender_id=tender_id,
            currency=data.currency,
            items=data.items,
            updated_at=utc_now_naive(),
        )
        self.quotations[(supplier_id, tender_id)] = guardada
        return guardada
