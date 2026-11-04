"""Programación de resúmenes de licitaciones (plan 233, decisión 4)."""

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from app.application.repositories.attachment_processing_job_repository import (
    IAttachmentProcessingJobRepository,
)
from app.application.repositories.tender_digest_repository import (
    ITenderDigestRepository,
)
from app.application.services.attachment_processing_notifier import (
    IAttachmentProcessingNotifier,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentVisibility,
)
from app.domain.entities.attachment_processing import PRIORIDAD_RESUMEN
from app.shared.datetime_utils import utc_now_naive


class ScheduleTenderDigestsUseCase:
    def __init__(
        self,
        *,
        jobs: IAttachmentProcessingJobRepository,
        digests: ITenderDigestRepository,
        notifier: IAttachmentProcessingNotifier,
        clock: Callable[[], datetime] = utc_now_naive,
    ) -> None:
        self._jobs = jobs
        self._digests = digests
        self._notifier = notifier
        self._clock = clock

    async def for_extracted_file(self, file: AttachmentFile) -> None:
        if file.visibility == AttachmentVisibility.SHARED:
            await self.after_visibility_change(file.tender_id)
        else:
            if await self._jobs.enqueue_digest(
                tender_id=file.tender_id,
                workspace_id=file.workspace_id,
                priority=PRIORIDAD_RESUMEN,
                now=self._clock(),
            ):
                self._notifier.notify()

    async def after_visibility_change(self, tender_id: UUID) -> None:
        workspaces = await self._digests.workspaces_with_current(tender_id)
        targets: list[UUID | None] = [None, *workspaces]
        encolado = False
        ahora = self._clock()
        for ws in targets:
            if await self._jobs.enqueue_digest(
                tender_id=tender_id,
                workspace_id=ws,
                priority=PRIORIDAD_RESUMEN,
                now=ahora,
            ):
                encolado = True
        if encolado:
            self._notifier.notify()
