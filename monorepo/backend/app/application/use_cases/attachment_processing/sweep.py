"""Barrido periódico de la cola de procesamiento de anexos (plan 233, decisión 4)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from app.application.services.attachment_processing_notifier import (
    IAttachmentProcessingNotifier,
)
from app.application.use_cases.attachment_processing.unit import UnitFactory
from app.domain.entities.attachment_extraction import EXTRACTION_PROMPT_VERSION
from app.domain.entities.attachment_processing import (
    PLAZO_DE_TRABAJO_COLGADO,
    PRIORIDAD_BARRIDO,
    RETENCION_DE_TRABAJOS,
)
from app.shared.datetime_utils import utc_now_naive


@dataclass(frozen=True)
class SweepResult:
    recovered: int
    enqueued: int
    purged: int


class SweepAttachmentProcessingUseCase:
    def __init__(
        self,
        *,
        units: UnitFactory,
        notifier: IAttachmentProcessingNotifier,
        prompt_version: str = EXTRACTION_PROMPT_VERSION,
        clock: Callable[[], datetime] = utc_now_naive,
        batch: int = 50,
    ) -> None:
        self._units = units
        self._notifier = notifier
        self._prompt_version = prompt_version
        self._clock = clock
        self._batch = batch

    async def execute(self) -> SweepResult:
        ahora = self._clock()

        async with self._units() as u:
            recovered = await u.jobs.recover_stale(
                locked_before=ahora - PLAZO_DE_TRABAJO_COLGADO,
                now=ahora,
            )

        enqueued = 0
        async with self._units() as u:
            missing = await u.jobs.files_missing_extraction(
                prompt_version=self._prompt_version,
                limit=self._batch,
            )
            for file_id, tender_id in missing:
                if await u.jobs.enqueue_extract(
                    attachment_file_id=file_id,
                    tender_id=tender_id,
                    priority=PRIORIDAD_BARRIDO,
                    now=ahora,
                ):
                    enqueued += 1

        async with self._units() as u:
            purged = await u.jobs.purge_finished(
                before=ahora - RETENCION_DE_TRABAJOS
            )

        if recovered > 0 or enqueued > 0:
            self._notifier.notify()

        return SweepResult(recovered=recovered, enqueued=enqueued, purged=purged)
