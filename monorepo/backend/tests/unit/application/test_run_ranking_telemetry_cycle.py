import pytest

from app.application.use_cases.ranking_telemetry.run_ranking_telemetry_cycle import (
    run_ranking_telemetry_cycle,
)
from app.domain.entities.ranking_telemetry import PurgeCounts


@pytest.mark.asyncio
async def test_corre_ndcg_prioridad_y_purga_en_ese_orden():
    llamadas: list[str] = []

    async def ndcg() -> int:
        llamadas.append("ndcg")
        return 4

    async def prioridad() -> int:
        llamadas.append("prioridad")
        return 7

    async def purga() -> PurgeCounts:
        llamadas.append("purga")
        return PurgeCounts(impressions=1)

    resultado = await run_ranking_telemetry_cycle(
        compute_metrics=ndcg, compute_priority=prioridad, purge=purga
    )

    assert llamadas == ["ndcg", "prioridad", "purga"]
    assert resultado.metrics_written == 4
    assert resultado.priority_snapshots == 7
    assert resultado.purged == PurgeCounts(impressions=1)
    assert resultado.failures == ()


@pytest.mark.asyncio
async def test_un_fallo_no_detiene_a_los_demas():
    llamadas: list[str] = []

    async def ndcg() -> int:
        llamadas.append("ndcg")
        return 4

    async def prioridad() -> int:
        raise RuntimeError("boom")

    async def purga() -> PurgeCounts:
        llamadas.append("purga")
        return PurgeCounts(interactions=2)

    resultado = await run_ranking_telemetry_cycle(
        compute_metrics=ndcg, compute_priority=prioridad, purge=purga
    )

    assert llamadas == ["ndcg", "purga"]
    assert resultado.failures == ("prioridad: boom",)
    assert resultado.metrics_written == 4
    assert resultado.priority_snapshots == 0
    assert resultado.purged == PurgeCounts(interactions=2)
