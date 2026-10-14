"""Calcula el NDCG@10 de los rankings servidos cada día de Chile (plan 233, decisión 8)."""

import asyncio
from collections import defaultdict
from collections.abc import Callable
from datetime import date, datetime, timedelta

from app.application.repositories.ranking_telemetry_repository import (
    IRankingTelemetryRepository,
)
from app.application.services.ranking_metrics_service import RankingMetricsService
from app.domain.entities.ranking_telemetry import (
    ATTRIBUTION_WINDOW,
    RankingImpression,
    RankingMetricDaily,
)
from app.shared.datetime_utils import chile_date, chile_day_bounds_utc, utc_now_naive


class ComputeDailyRankingMetricsUseCase:
    """Un NDCG@10 por (día de Chile, versión del modelo).

    Se calcula sobre el orden servido, que es lo que produjo el modelo. Es
    idempotente: reescribe la fila del día, y una interacción puede llegar hasta
    7 días después de servido el ranking, por eso `execute_recent` recalcula la
    semana completa.
    """

    def __init__(
        self,
        repo: IRankingTelemetryRepository,
        metrics: RankingMetricsService,
        now: Callable[[], datetime] = utc_now_naive,
    ) -> None:
        self.repo = repo
        self.metrics = metrics
        self.now = now

    async def execute_for_day(self, day: date) -> list[RankingMetricDaily]:
        start, end = chile_day_bounds_utc(day)
        impressions = await self.repo.list_impressions_between(start, end)
        ranking_ids = sorted({i.ranking_id for i in impressions})
        interactions = await self.repo.list_attributed_interactions(ranking_ids)

        by_version: dict[str, list[RankingImpression]] = defaultdict(list)
        for impression in impressions:
            by_version[impression.model_version].append(impression)

        written: list[RankingMetricDaily] = []
        for version in sorted(by_version):
            version_impressions = by_version[version]
            version_rankings = {i.ranking_id for i in version_impressions}
            version_interactions = [
                i for i in interactions if i.ranking_id in version_rankings
            ]
            # El bootstrap es CPU y la API corre con un solo worker: fuera del loop.
            evaluation = await asyncio.to_thread(
                self.metrics.evaluate, version_impressions, version_interactions
            )
            if evaluation is None:
                # Sin ranking con ganancia no se escribe, y tampoco se pisa una
                # métrica ya guardada: lo crudo de ese día pudo purgarse.
                continue
            metric = RankingMetricDaily(
                day=day,
                model_version=version,
                ndcg_at_10=evaluation.ndcg_at_10,
                ci_low=evaluation.ci_low,
                ci_high=evaluation.ci_high,
                rankings_evaluated=evaluation.rankings_evaluated,
                rankings_served=evaluation.rankings_served,
                computed_at=self.now(),
            )
            await self.repo.upsert_daily_metric(metric)
            written.append(metric)
        return written

    async def execute_recent(
        self,
        days: int = ATTRIBUTION_WINDOW.days,
        include_today: bool = False,
    ) -> list[RankingMetricDaily]:
        """Recalcula los últimos `days` días completos de Chile, del más viejo al más nuevo."""
        today = chile_date(self.now())
        offsets = range(days, -1 if include_today else 0, -1)
        written: list[RankingMetricDaily] = []
        for offset in offsets:
            written.extend(await self.execute_for_day(today - timedelta(days=offset)))
        return written
