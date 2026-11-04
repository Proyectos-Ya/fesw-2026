from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest

from app.application.use_cases.ranking_telemetry.purge_ranking_telemetry import (
    PurgeRankingTelemetryUseCase,
)
from app.domain.entities.ranking_telemetry import (
    AttachmentPriorityShadow,
    InteractionKind,
    PurgeCounts,
    RankingImpression,
    RankingMetricDaily,
    TenderInteraction,
)
from tests.unit.application.fakes import InMemoryRankingTelemetryRepository

AHORA = datetime(2026, 10, 3, 12, 0)
CORTE = AHORA - timedelta(days=90)


@pytest.mark.asyncio
async def test_borra_lo_crudo_de_mas_de_90_dias_y_conserva_los_agregados():
    repo = InMemoryRankingTelemetryRepository()
    for cuando in (
        CORTE - timedelta(seconds=1),  # se borra
        CORTE,  # se conserva: el criterio es `<`
        AHORA - timedelta(days=89),  # se conserva
    ):
        repo.impressions.append(
            RankingImpression(
                ranking_id=uuid4(),
                supplier_id=uuid4(),
                user_id=uuid4(),
                tender_id=uuid4(),
                position=1,
                model_version="m1",
                created_at=cuando,
            )
        )
        repo.interactions.append(
            TenderInteraction(
                user_id=uuid4(),
                tender_id=uuid4(),
                kind=InteractionKind.DETALLE,
                source="matches",
                created_at=cuando,
            )
        )
        repo.snapshots.append(
            AttachmentPriorityShadow(
                tender_id=uuid4(), computed_at=cuando, priority=1.0, components={}
            )
        )
    repo.metrics[(date(2026, 3, 1), "m1")] = RankingMetricDaily(
        day=date(2026, 3, 1),
        model_version="m1",
        ndcg_at_10=0.5,
        ci_low=0.4,
        ci_high=0.6,
        rankings_evaluated=3,
        rankings_served=10,
    )

    borrado = await PurgeRankingTelemetryUseCase(repo, now=lambda: AHORA).execute()

    assert borrado == PurgeCounts(impressions=1, interactions=1, priority_snapshots=1)
    assert len(repo.impressions) == 2
    assert len(repo.interactions) == 2
    assert len(repo.snapshots) == 2
    assert (date(2026, 3, 1), "m1") in repo.metrics
