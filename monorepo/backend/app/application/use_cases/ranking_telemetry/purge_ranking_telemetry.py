"""Purga lo crudo de la telemetría del ranking a los 90 días (plan 233, decisión 8)."""

from collections.abc import Callable
from datetime import datetime

from app.application.repositories.ranking_telemetry_repository import (
    IRankingTelemetryRepository,
)
from app.domain.entities.ranking_telemetry import RAW_RETENTION, PurgeCounts
from app.shared.datetime_utils import utc_now_naive


class PurgeRankingTelemetryUseCase:
    """Borra impresiones, interacciones y snapshots de más de 90 días.

    Las métricas diarias quedan: son agregados sin datos personales.
    """

    def __init__(
        self,
        repo: IRankingTelemetryRepository,
        now: Callable[[], datetime] = utc_now_naive,
    ) -> None:
        self.repo = repo
        self.now = now

    async def execute(self) -> PurgeCounts:
        return await self.repo.purge_before(self.now() - RAW_RETENTION)
