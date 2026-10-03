"""NDCG@10 diario por versión del modelo, sobre el día de Chile."""

from datetime import date, datetime
from uuid import UUID, uuid4

import pytest

from app.application.services.ranking_metrics_service import RankingMetricsService
from app.application.use_cases.ranking_telemetry.compute_daily_ranking_metrics import (
    ComputeDailyRankingMetricsUseCase,
)
from app.domain.entities.ranking_telemetry import (
    InteractionKind,
    RankingImpression,
    TenderInteraction,
)
from tests.unit.application.fakes import InMemoryRankingTelemetryRepository

DIA = date(2026, 10, 2)
# Las 09:00 del 3 de octubre en Chile (UTC-3).
AHORA = datetime(2026, 10, 3, 12, 0)


def _servir(
    repo: InMemoryRankingTelemetryRepository,
    *,
    version: str,
    cuando: datetime,
    n: int,
) -> tuple[UUID, list[UUID]]:
    """Sirve un ranking de `n` licitaciones y devuelve (ranking_id, tender_ids)."""
    ranking, user, supplier = uuid4(), uuid4(), uuid4()
    tenders = [uuid4() for _ in range(n)]
    for posicion, tender in enumerate(tenders, start=1):
        repo.impressions.append(
            RankingImpression(
                ranking_id=ranking,
                supplier_id=supplier,
                user_id=user,
                tender_id=tender,
                position=posicion,
                model_version=version,
                created_at=cuando,
            )
        )
    return ranking, tenders


def _interaccion(
    repo: InMemoryRankingTelemetryRepository,
    ranking: UUID,
    tender: UUID,
    kind: InteractionKind,
) -> None:
    repo.interactions.append(
        TenderInteraction(
            user_id=uuid4(),
            tender_id=tender,
            kind=kind,
            ranking_id=ranking,
            position=1,
            source="matches",
            created_at=AHORA,
        )
    )


def _caso(
    repo: InMemoryRankingTelemetryRepository,
) -> ComputeDailyRankingMetricsUseCase:
    return ComputeDailyRankingMetricsUseCase(
        repo, RankingMetricsService(), now=lambda: AHORA
    )


@pytest.mark.asyncio
async def test_un_ndcg_por_version_sin_los_rankings_vacios():
    repo = InMemoryRankingTelemetryRepository()
    a, ta = _servir(repo, version="m1", cuando=datetime(2026, 10, 2, 15, 0), n=5)
    _servir(repo, version="m1", cuando=datetime(2026, 10, 2, 16, 0), n=3)  # B: vacío
    c, tc = _servir(repo, version="m2", cuando=datetime(2026, 10, 2, 17, 0), n=1)
    _interaccion(repo, a, ta[1], InteractionKind.ANALISIS)
    _interaccion(repo, a, ta[3], InteractionKind.DETALLE)
    _interaccion(repo, a, ta[4], InteractionKind.GUARDAR)
    _interaccion(repo, c, tc[0], InteractionKind.DETALLE)

    escritas = await _caso(repo).execute_for_day(DIA)

    assert {
        (m.model_version, m.rankings_evaluated, m.rankings_served) for m in escritas
    } == {("m1", 1, 2), ("m2", 1, 1)}
    assert repo.metrics[(DIA, "m1")].ndcg_at_10 == pytest.approx(0.6504121821761035)
    assert repo.metrics[(DIA, "m2")].ndcg_at_10 == pytest.approx(1.0)
    assert repo.metrics[(DIA, "m1")].computed_at == AHORA


@pytest.mark.asyncio
async def test_el_dia_es_el_de_chile_no_el_utc():
    repo = InMemoryRankingTelemetryRepository()
    # 02:30 UTC del 3 es el 2 a las 23:30 en Chile.
    r, t = _servir(repo, version="m1", cuando=datetime(2026, 10, 3, 2, 30), n=1)
    _interaccion(repo, r, t[0], InteractionKind.DETALLE)

    del_2 = await _caso(repo).execute_for_day(date(2026, 10, 2))
    del_3 = await _caso(repo).execute_for_day(date(2026, 10, 3))

    assert len(del_2) == 1
    assert del_3 == []


@pytest.mark.asyncio
async def test_correr_dos_veces_el_mismo_dia_no_duplica_filas():
    repo = InMemoryRankingTelemetryRepository()
    a, ta = _servir(repo, version="m1", cuando=datetime(2026, 10, 2, 15, 0), n=2)
    c, tc = _servir(repo, version="m2", cuando=datetime(2026, 10, 2, 15, 0), n=2)
    _interaccion(repo, a, ta[0], InteractionKind.DETALLE)
    _interaccion(repo, c, tc[0], InteractionKind.DETALLE)

    await _caso(repo).execute_for_day(DIA)
    await _caso(repo).execute_for_day(DIA)

    assert len(repo.metrics) == 2


@pytest.mark.asyncio
async def test_un_dia_sin_datos_crudos_no_pisa_la_metrica_existente():
    # Lo crudo pudo purgarse: recalcular no puede borrar el agregado ya guardado.
    repo = InMemoryRankingTelemetryRepository()
    a, ta = _servir(repo, version="m1", cuando=datetime(2026, 10, 2, 15, 0), n=2)
    _interaccion(repo, a, ta[0], InteractionKind.DETALLE)
    await _caso(repo).execute_for_day(DIA)
    original = repo.metrics[(DIA, "m1")]

    repo.impressions.clear()
    repo.interactions.clear()
    escritas = await _caso(repo).execute_for_day(DIA)

    assert escritas == []
    assert repo.metrics[(DIA, "m1")] is original


@pytest.mark.asyncio
async def test_execute_recent_recalcula_los_ultimos_7_dias_completos():
    repo = InMemoryRankingTelemetryRepository()
    for cuando in (
        datetime(2026, 9, 25, 15, 0),  # 8 días antes: fuera de la ventana
        datetime(2026, 9, 26, 15, 0),  # el primer día de la ventana
        datetime(2026, 10, 3, 11, 0),  # hoy
    ):
        r, t = _servir(repo, version="m1", cuando=cuando, n=1)
        _interaccion(repo, r, t[0], InteractionKind.DETALLE)

    escritas = await _caso(repo).execute_recent(days=7)
    con_hoy = await _caso(repo).execute_recent(days=7, include_today=True)

    assert {m.day for m in escritas} == {date(2026, 9, 26)}
    assert {m.day for m in con_hoy} == {date(2026, 9, 26), date(2026, 10, 3)}
