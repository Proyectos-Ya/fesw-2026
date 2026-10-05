"""Listener para encolar extracción cuando un archivo pasa a STORED (plan 233, decisión 4)."""

from collections.abc import Callable
from datetime import datetime

from app.application.repositories.attachment_processing_job_repository import (
    IAttachmentProcessingJobRepository,
)
from app.application.services.attachment_processing_notifier import (
    IAttachmentProcessingNotifier,
)
from app.application.services.attachment_stored_listener import (
    IAttachmentStoredListener,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
)
from app.domain.entities.attachment_processing import (
    PRIORIDAD_BARRIDO,
    PRIORIDAD_EXTENSION,
    PRIORIDAD_SUBIDA_MANUAL,
)
from app.shared.datetime_utils import utc_now_naive

PRIORIDAD_POR_FUENTE = {
    AttachmentFileSource.MANUAL: PRIORIDAD_SUBIDA_MANUAL,
    AttachmentFileSource.EXTENSION: PRIORIDAD_EXTENSION,
    AttachmentFileSource.LEGACY_CHAT: PRIORIDAD_BARRIDO,
}


class EnqueueExtractionOnStored(IAttachmentStoredListener):
    """Decisión 4 colgada de D18 de la decisión 2: corre después del commit de `stored`."""

    def __init__(
        self,
        *,
        jobs: IAttachmentProcessingJobRepository,
        notifier: IAttachmentProcessingNotifier,
        clock: Callable[[], datetime] = utc_now_naive,
    ) -> None:
        self.jobs = jobs
        self.notifier = notifier
        self.clock = clock

    async def on_stored(self, file: AttachmentFile) -> None:
        if file.status != AttachmentFileStatus.STORED:
            return
        priority = PRIORIDAD_POR_FUENTE.get(file.source, PRIORIDAD_BARRIDO)
        if await self.jobs.enqueue_extract(
            attachment_file_id=file.id,
            tender_id=file.tender_id,
            priority=priority,
            now=self.clock(),
        ):
            self.notifier.notify()
