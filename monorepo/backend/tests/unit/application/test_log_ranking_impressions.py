from datetime import datetime
from uuid import uuid4

import pytest

from app.application.use_cases.ranking_telemetry.log_ranking_impressions import (
    LogRankingImpressionsUseCase,
)
from app.domain.entities.matching_result import MatchingResult
from tests.unit.application.fakes import InMemoryRankingTelemetryRepository

SERVIDO = datetime(2026, 10, 3, 12, 0)


def _resultado(supplier_id, score: float) -> MatchingResult:
    return MatchingResult(
        supplier_id=supplier_id,
        tender_id=uuid4(),
        final_score=score,
        model_version="m1",
    )


@pytest.mark.asyncio
async def test_guarda_las_posiciones_en_el_orden_servido():
    repo = InMemoryRankingTelemetryRepository()
    supplier, user, ranking = uuid4(), uuid4(), uuid4()
    resultados = [_resultado(supplier, s) for s in (0.9, 0.8, 0.7)]

    guardadas = await LogRankingImpressionsUseCase(repo).execute(
        ranking_id=ranking, user_id=user, results=resultados, served_at=SERVIDO
    )

    assert guardadas == 3
    assert [i.position for i in repo.impressions] == [1, 2, 3]
    assert [i.tender_id for i in repo.impressions] == [r.tender_id for r in resultados]
    assert [i.score for i in repo.impressions] == [0.9, 0.8, 0.7]
    assert {i.created_at for i in repo.impressions} == {SERVIDO}
    assert {i.ranking_id for i in repo.impressions} == {ranking}
    assert {i.user_id for i in repo.impressions} == {user}
    assert {i.supplier_id for i in repo.impressions} == {supplier}
    assert {i.model_version for i in repo.impressions} == {"m1"}


@pytest.mark.asyncio
async def test_una_lista_vacia_no_escribe_nada():
    class RepoQueNoDebeUsarse(InMemoryRankingTelemetryRepository):
        async def save_impressions(self, impressions):
            raise AssertionError("no debería llamarse con una lista vacía")

    guardadas = await LogRankingImpressionsUseCase(RepoQueNoDebeUsarse()).execute(
        ranking_id=uuid4(), user_id=uuid4(), results=[], served_at=SERVIDO
    )

    assert guardadas == 0
