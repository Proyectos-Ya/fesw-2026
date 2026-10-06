"""Lo que pasa con una exportación después de responder (HdU 19, criterios 8 y 9)."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from uuid import UUID

from app.application.repositories.export_job_repository import IExportJobRepository
from app.application.services.email_service import EmailMessage, IEmailService
from app.application.services.email_templates import (
    ExportReadyItem,
    build_export_failed_html_body,
    build_export_failed_subject,
    build_export_failed_text_body,
    build_export_ready_html_body,
    build_export_ready_subject,
    build_export_ready_text_body,
)
from app.application.use_cases.exports.export_tender import ExportFile
from app.domain.entities.export_job import ExportFormat, ExportJob, ExportJobStatus
from app.domain.errors.export_errors import ExportFileUnavailable, ExportJobNotFound
from app.domain.errors.notification_errors import EmailDeliveryError
from app.shared.datetime_utils import utc_now_naive

logger = logging.getLogger(__name__)

# Un trabajo en proceso más joven que esto puede ser de una instancia anterior que
# sigue viva durante el despliegue: el arranque no lo toca.
_GRACIA_REINICIO = timedelta(minutes=15)
_INTERRUMPIDA = "La API se apagó durante la generación."

_ETIQUETAS = {ExportFormat.PDF: "PDF", ExportFormat.XLSX: "Excel"}


class CompleteExportJobUseCase:
    """Espera el archivo que siguió generándose, lo guarda y avisa por correo.

    El correo va directo y no por la cola de alertas: lo pidió el usuario, y la
    cola lo descartaría si tiene las alertas por correo apagadas.
    """

    def __init__(
        self,
        jobs: IExportJobRepository,
        email: IEmailService,
        base_url: str,
        now: Callable[[], datetime] = utc_now_naive,
    ) -> None:
        self.jobs = jobs
        self.email = email
        self.base_url = base_url
        self.now = now

    async def execute(
        self, job: ExportJob, render: Awaitable[bytes], recipient: str, tender_name: str
    ) -> ExportJob:
        item = ExportReadyItem(
            job_id=job.id, tender_name=tender_name, format_label=_ETIQUETAS[job.format]
        )
        try:
            content = await render
        except asyncio.CancelledError:
            # La API se está apagando: se deja constancia para que nadie espere un
            # archivo que no llegará. Sin correo, el proceso se está cerrando.
            await self.jobs.save(job.fallido(_INTERRUMPIDA, self.now()))
            raise
        except Exception as error:
            logger.exception("Falló la exportación %s", job.id)
            fallido = await self.jobs.save(job.fallido(str(error) or type(error).__name__, self.now()))
            await self._avisar(
                EmailMessage(
                    to=recipient,
                    subject=build_export_failed_subject(item),
                    text_body=build_export_failed_text_body(item),
                    html_body=build_export_failed_html_body(item),
                )
            )
            return fallido

        listo = await self.jobs.save(job.listo(content, self.now()))
        await self._avisar(
            EmailMessage(
                to=recipient,
                subject=build_export_ready_subject(item),
                text_body=build_export_ready_text_body(item, self.base_url),
                html_body=build_export_ready_html_body(item, self.base_url),
            )
        )
        return listo

    async def _avisar(self, mensaje: EmailMessage) -> None:
        # El archivo ya quedó guardado: si el correo no sale, igual se puede
        # descargar desde la app, que consulta el estado mientras está abierta.
        try:
            await self.email.send(mensaje)
        except EmailDeliveryError:
            logger.warning("No se pudo enviar el aviso de exportación a %s", mensaje.to)


class GetExportJobUseCase:
    def __init__(self, jobs: IExportJobRepository) -> None:
        self.jobs = jobs

    async def execute(
        self, user_id: UUID, job_id: UUID, with_content: bool = False
    ) -> ExportJob:
        job = await self.jobs.get(job_id, with_content=with_content)
        if job is None or job.user_id != user_id:
            raise ExportJobNotFound()
        return job


class DownloadExportFileUseCase:
    def __init__(
        self, jobs: IExportJobRepository, now: Callable[[], datetime] = utc_now_naive
    ) -> None:
        self.jobs = jobs
        self.now = now

    async def execute(self, user_id: UUID, job_id: UUID) -> ExportFile:
        job = await GetExportJobUseCase(self.jobs).execute(user_id, job_id, with_content=True)
        if job.status is ExportJobStatus.PROCESSING:
            raise ExportFileUnavailable("processing")
        if job.status is ExportJobStatus.FAILED:
            raise ExportFileUnavailable("failed")
        if not job.descargable(self.now()) or job.content is None:
            raise ExportFileUnavailable("expired")
        return ExportFile(
            file_name=job.file_name, media_type=job.format.media_type, content=job.content
        )


class ReconcileExportJobsUseCase:
    """Al arrancar la API: nada puede seguir "en proceso" después de un reinicio."""

    def __init__(
        self, jobs: IExportJobRepository, now: Callable[[], datetime] = utc_now_naive
    ) -> None:
        self.jobs = jobs
        self.now = now

    async def execute(self) -> tuple[int, int]:
        ahora = self.now()
        colgados = await self.jobs.fail_stale(ahora, ahora - _GRACIA_REINICIO)
        return colgados, await self.jobs.purge_expired(ahora)
