"""Caso de uso de procesamiento del siguiente trabajo de la cola (plan 233, decisión 4)."""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from app.application.services.attachment_processing_notifier import (
    IAttachmentProcessingNotifier,
)
from app.application.use_cases.attachment_processing.build_tender_digest import (
    BuildTenderDigestUseCase,
)
from app.application.use_cases.attachment_processing.extract_attachment import (
    ExtractAttachmentUseCase,
)
from app.application.use_cases.attachment_processing.schedule_tender_digests import (
    ScheduleTenderDigestsUseCase,
)
from app.application.use_cases.attachment_processing.unit import UnitFactory
from app.domain.entities.attachment_processing import (
    HANDLED_KINDS,
    ProcessingJobKind,
    agoto_intentos,
    proximo_intento,
)
from app.domain.errors.attachment_processing_errors import (
    AttachmentExtractionRejected,
    AttachmentExtractionUnavailable,
    InvalidExtractionResponse,
)
from app.domain.errors.tender_errors import TenderNotFound
from app.domain.services.gemini_budget import dia_del_tope
from app.shared.datetime_utils import utc_now_naive

logger = logging.getLogger(__name__)


class ProcessNextAttachmentJobUseCase:
    def __init__(
        self,
        *,
        units: UnitFactory,
        extract: ExtractAttachmentUseCase,
        notifier: IAttachmentProcessingNotifier,
        clock: Callable[[], datetime] = utc_now_naive,
    ) -> None:
        self._units = units
        self._extract = extract
        self._notifier = notifier
        self._clock = clock

    async def execute(self) -> bool:
        ahora = self._clock()
        async with self._units() as u:
            job = await u.jobs.claim_next(now=ahora, kinds=HANDLED_KINDS)
        if job is None:
            return False

        if job.kind == ProcessingJobKind.EXTRACT:
            if job.attachment_file_id is None:
                async with self._units() as u:
                    await u.jobs.fail(
                        job.id,
                        error="Trabajo extract sin attachment_file_id",
                        now=ahora,
                    )
                return True

            try:
                outcome = await self._extract.execute(job.attachment_file_id)
            except AttachmentExtractionUnavailable as exc:
                if exc.rate_limited:
                    wait_secs = exc.retry_after_seconds or 900
                    not_before = ahora + timedelta(seconds=wait_secs)
                    async with self._units() as u:
                        await u.jobs.defer(
                            job.id,
                            not_before=not_before,
                            reason=str(exc)[:500],
                            now=ahora,
                        )
                else:
                    if agoto_intentos(job):
                        async with self._units() as u:
                            await u.jobs.fail(
                                job.id, error=str(exc)[:500], now=ahora
                            )
                    else:
                        not_before = (
                            ahora + timedelta(seconds=exc.retry_after_seconds)
                            if exc.retry_after_seconds
                            else proximo_intento(job.kind, job.attempts, ahora)
                        )
                        async with self._units() as u:
                            await u.jobs.retry(
                                job.id,
                                not_before=not_before,
                                error=str(exc)[:500],
                                now=ahora,
                            )
                return True
            except InvalidExtractionResponse as exc:
                if agoto_intentos(job):
                    async with self._units() as u:
                        await u.jobs.fail(
                            job.id, error=str(exc)[:500], now=ahora
                        )
                else:
                    not_before = proximo_intento(job.kind, job.attempts, ahora)
                    async with self._units() as u:
                        await u.jobs.retry(
                            job.id,
                            not_before=not_before,
                            error=str(exc)[:500],
                            now=ahora,
                        )
                return True
            except AttachmentExtractionRejected as exc:
                async with self._units() as u:
                    await u.jobs.fail(job.id, error=str(exc)[:500], now=ahora)
                return True
            except Exception as exc:
                logger.exception(
                    "Error inesperado al procesar anexo %s: %s",
                    job.attachment_file_id,
                    exc,
                )
                if agoto_intentos(job):
                    async with self._units() as u:
                        await u.jobs.fail(
                            job.id, error=str(exc)[:500], now=ahora
                        )
                else:
                    not_before = proximo_intento(job.kind, job.attempts, ahora)
                    async with self._units() as u:
                        await u.jobs.retry(
                            job.id,
                            not_before=not_before,
                            error=str(exc)[:500],
                            now=ahora,
                        )
                return True

            if outcome.kind == "deferred_budget":
                budget = self._extract._daily_budget
                dia_siguiente = dia_del_tope(ahora) + timedelta(days=1)
                reason = (
                    f"Tope diario de Gemini agotado ({budget} llamadas); se"
                    f" retoma el {dia_siguiente:%Y-%m-%d} (hora de Chile)."
                )
                not_before = outcome.not_before or ahora + timedelta(hours=12)
                async with self._units() as u:
                    await u.jobs.defer(
                        job.id,
                        not_before=not_before,
                        reason=reason,
                        now=ahora,
                    )
            elif outcome.kind in ("saved", "reused", "already_done"):
                if outcome.file is not None:
                    async with self._units() as u:
                        schedule = ScheduleTenderDigestsUseCase(
                            jobs=u.jobs,
                            digests=u.digests,
                            notifier=self._notifier,
                            clock=self._clock,
                        )
                        await schedule.for_extracted_file(outcome.file)
                async with self._units() as u:
                    await u.jobs.complete(job.id, now=ahora)
            else:
                async with self._units() as u:
                    await u.jobs.complete(job.id, now=ahora)
            return True

        if job.kind == ProcessingJobKind.DIGEST:
            try:
                async with self._units() as u:
                    build_use_case = BuildTenderDigestUseCase(
                        tenders=u.tenders,
                        extractions=u.extractions,
                        digests=u.digests,
                        clock=self._clock,
                    )
                    await build_use_case.execute(
                        job.tender_id, workspace_id=job.workspace_id
                    )
            except TenderNotFound:
                pass
            except Exception as exc:
                logger.exception(
                    "Error al construir resumen de licitación %s: %s",
                    job.tender_id,
                    exc,
                )
                if agoto_intentos(job):
                    async with self._units() as u:
                        await u.jobs.fail(
                            job.id, error=str(exc)[:500], now=ahora
                        )
                else:
                    not_before = proximo_intento(job.kind, job.attempts, ahora)
                    async with self._units() as u:
                        await u.jobs.retry(
                            job.id,
                            not_before=not_before,
                            error=str(exc)[:500],
                            now=ahora,
                        )
                return True

            async with self._units() as u:
                await u.jobs.complete(job.id, now=ahora)
            return True

        return False
