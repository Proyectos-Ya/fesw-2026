"""Un ciclo completo de la telemetría del ranking (plan 233, decisión 8).

Lo comparten el bucle del lifespan y `scripts/ranking_telemetry.py`.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.domain.entities.ranking_telemetry import PurgeCounts


@dataclass(frozen=True)
class RankingTelemetryCycleResult:
    metrics_written: int = 0
    priority_snapshots: int = 0
    purged: PurgeCounts | None = None
    failures: tuple[str, ...] = ()  # p. ej. ("ndcg: <error>",)


async def run_ranking_telemetry_cycle(
    *,
    compute_metrics: Callable[[], Awaitable[int]],
    compute_priority: Callable[[], Awaitable[int]],
    purge: Callable[[], Awaitable[PurgeCounts]],
) -> RankingTelemetryCycleResult:
    """NDCG, prioridad en sombra y purga, en ese orden.

    Cada trabajo corre aislado: un fallo se anota en `failures` y no detiene a los
    demás, porque son independientes entre sí.
    """
    failures: list[str] = []
    metrics_written = 0
    priority_snapshots = 0
    purged: PurgeCounts | None = None

    try:
        metrics_written = await compute_metrics()
    except Exception as error:
        failures.append(f"ndcg: {error}")
    try:
        priority_snapshots = await compute_priority()
    except Exception as error:
        failures.append(f"prioridad: {error}")
    try:
        purged = await purge()
    except Exception as error:
        failures.append(f"purga: {error}")

    return RankingTelemetryCycleResult(
        metrics_written=metrics_written,
        priority_snapshots=priority_snapshots,
        purged=purged,
        failures=tuple(failures),
    )
