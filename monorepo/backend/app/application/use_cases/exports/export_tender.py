"""Exportar una licitación a PDF o Excel (HdU 19, criterios 3, 4, 5, 8 y 9)."""

import asyncio
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.application.repositories.export_job_repository import IExportJobRepository
from app.application.services.export_background import IExportBackground
from app.application.services.export_renderers import IExcelRenderer, IPdfRenderer
from app.application.use_cases.exports.build_export_snapshot import (
    BuildExportSnapshotUseCase,
)
from app.application.use_cases.exports.export_snapshot import ExportSection
from app.domain.entities.export_job import ExportFormat, ExportJob
from app.domain.entities.supplier_member import WorkspaceContext
from app.domain.errors.export_errors import (
    ExportGenerationFailed,
    ExportSectionsRequired,
)
from app.shared.datetime_utils import utc_now_naive


@dataclass(frozen=True)
class ExportFile:
    """Estuvo listo a tiempo: se entrega en la misma respuesta."""

    file_name: str
    media_type: str
    content: bytes


@dataclass(frozen=True)
class ExportQueued:
    """Se pasó del umbral: sigue en segundo plano y avisa por correo."""

    job: ExportJob


ExportOutcome = ExportFile | ExportQueued


def export_file_name(code: str, format: ExportFormat) -> str:
    # El código de Mercado Público puede traer "/", que no va en un nombre de archivo.
    seguro = re.sub(r"[^A-Za-z0-9_-]", "_", code)
    return f"licitacion-{seguro}.{format.value}"


class ExportTenderUseCase:
    """Genera el archivo y, si tarda más del umbral, lo termina en segundo plano.

    El render corre en un hilo aparte: la API atiende con un solo worker, y un
    PDF generándose en el event loop frenaría todas las demás peticiones. La
    tarea se espera con `shield`, así que vencer el umbral no la cancela: sigue
    corriendo y la recoge `IExportBackground`.
    """

    def __init__(
        self,
        snapshots: BuildExportSnapshotUseCase,
        jobs: IExportJobRepository,
        pdf_renderer: IPdfRenderer,
        excel_renderer: IExcelRenderer,
        background: IExportBackground,
        inline_timeout_seconds: float,
        now: Callable[[], datetime] = utc_now_naive,
    ) -> None:
        self.snapshots = snapshots
        self.jobs = jobs
        self.pdf_renderer = pdf_renderer
        self.excel_renderer = excel_renderer
        self.background = background
        self.inline_timeout_seconds = inline_timeout_seconds
        self.now = now

    async def execute(
        self,
        ctx: WorkspaceContext,
        recipient_email: str,
        tender_id: UUID,
        format: ExportFormat,
        sections: Sequence[ExportSection],
    ) -> ExportOutcome:
        if format is ExportFormat.XLSX and not sections:
            raise ExportSectionsRequired()
        snapshot = await self.snapshots.execute(ctx, tender_id)

        if format is ExportFormat.PDF:
            tarea = asyncio.create_task(asyncio.to_thread(self.pdf_renderer.render, snapshot))
        else:
            tarea = asyncio.create_task(
                asyncio.to_thread(self.excel_renderer.render, snapshot, list(sections))
            )
        file_name = export_file_name(snapshot.tender.code, format)

        try:
            content = await asyncio.wait_for(
                asyncio.shield(tarea), timeout=self.inline_timeout_seconds
            )
        except TimeoutError:
            job = ExportJob.crear(
                user_id=ctx.user_id,
                supplier_id=ctx.active_supplier_id,
                tender_id=tender_id,
                format=format,
                sections=[s.value for s in sections],
                file_name=file_name,
                now=self.now(),
            )
            await self.jobs.save(job)
            self.background.schedule(job, tarea, recipient_email, snapshot.tender.name)
            return ExportQueued(job=job)
        except Exception as error:
            raise ExportGenerationFailed() from error

        return ExportFile(file_name=file_name, media_type=format.media_type, content=content)
