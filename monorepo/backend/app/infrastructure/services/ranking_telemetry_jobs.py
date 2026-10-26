"""Arma el ciclo de la telemetría del ranking con repositorios SQL.

Lo usan el bucle del lifespan y `scripts/ranking_telemetry.py`, así que corren
exactamente el mismo código.
"""

from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.services.attachment_priority_shadow_service import (
    AttachmentPriorityShadowService,
)
from app.application.services.ranking_metrics_service import RankingMetricsService
from app.application.use_cases.ranking_telemetry.compute_attachment_priority_shadow import (
    ComputeAttachmentPriorityShadowUseCase,
)
from app.application.use_cases.ranking_telemetry.compute_daily_ranking_metrics import (
    ComputeDailyRankingMetricsUseCase,
)
from app.application.use_cases.ranking_telemetry.purge_ranking_telemetry import (
    PurgeRankingTelemetryUseCase,
)
from app.application.use_cases.ranking_telemetry.run_ranking_telemetry_cycle import (
    RankingTelemetryCycleResult,
    run_ranking_telemetry_cycle,
)
from app.domain.entities.ranking_telemetry import ATTRIBUTION_WINDOW, PurgeCounts
from app.infrastructure.repositories.ranking_telemetry_repository import (
    SqlRankingTelemetryRepository,
)


def build_ranking_telemetry_cycle(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    ndcg_days: int = ATTRIBUTION_WINDOW.days,
    include_today: bool = False,
) -> Callable[[], Awaitable[RankingTelemetryCycleResult]]:
    """Arma el ciclo; cada trabajo abre y cierra su propia sesión.

    `ndcg_days` son los días completos de Chile que se recalculan (7 por
    defecto: una interacción puede llegar hasta 7 días después). `include_today`
    suma el día en curso, útil para probar a mano.
    """

    async def compute_metrics() -> int:
        async with session_maker() as session:
            escritas = await ComputeDailyRankingMetricsUseCase(
                SqlRankingTelemetryRepository(session), RankingMetricsService()
            ).execute_recent(days=ndcg_days, include_today=include_today)
            return len(escritas)

    async def compute_priority() -> int:
        async with session_maker() as session:
            return await ComputeAttachmentPriorityShadowUseCase(
                SqlRankingTelemetryRepository(session),
                AttachmentPriorityShadowService(),
            ).execute()

    async def purge() -> PurgeCounts:
        async with session_maker() as session:
            return await PurgeRankingTelemetryUseCase(
                SqlRankingTelemetryRepository(session)
            ).execute()

    async def cycle() -> RankingTelemetryCycleResult:
        return await run_ranking_telemetry_cycle(
            compute_metrics=compute_metrics,
            compute_priority=compute_priority,
            purge=purge,
        )

    return cycle
