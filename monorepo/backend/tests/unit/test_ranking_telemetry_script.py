"""El script manual comparte el ciclo del bucle y se niega a correr donde no debe."""

import argparse

import pytest

from app.application.use_cases.ranking_telemetry.run_ranking_telemetry_cycle import (
    RankingTelemetryCycleResult,
)
from app.domain.entities.ranking_telemetry import PurgeCounts
from scripts.ranking_telemetry import MAX_DIAS, correr, validar_dias


def _args(**extra) -> argparse.Namespace:
    base = {"dias": 7, "incluir_hoy": False, "confirmar_produccion": False}
    base.update(extra)
    return argparse.Namespace(**base)


class TestValidarDias:
    @pytest.mark.parametrize("dias", [0, -1, MAX_DIAS + 1, 91])
    def test_rechaza_lo_que_esta_fuera_de_1_a_90(self, dias):
        # Más atrás de 90 días la purga ya borró lo crudo.
        assert validar_dias(dias) is not None

    @pytest.mark.parametrize("dias", [1, 7, 90])
    def test_acepta_de_1_a_90(self, dias):
        assert validar_dias(dias) is None


class TestCorrer:
    async def test_un_ciclo_sin_fallos_sale_con_0(self, capsys):
        async def ciclo() -> RankingTelemetryCycleResult:
            return RankingTelemetryCycleResult(
                metrics_written=3,
                priority_snapshots=5,
                purged=PurgeCounts(impressions=1, interactions=2),
            )

        assert await correr(_args(), ciclo) == 0
        salida = capsys.readouterr().out
        assert "3" in salida
        assert "5" in salida

    async def test_un_fallo_sale_con_1_e_imprime_el_motivo(self, capsys):
        async def ciclo() -> RankingTelemetryCycleResult:
            return RankingTelemetryCycleResult(failures=("ndcg: x",))

        assert await correr(_args(), ciclo) == 1
        assert "ndcg: x" in capsys.readouterr().out


class TestMostrarMetricas:
    async def test_sin_metricas_muestra_mensaje(self, capsys):
        from tests.unit.application.fakes import InMemoryRankingTelemetryRepository
        from scripts.ranking_telemetry import mostrar_metricas

        repo = InMemoryRankingTelemetryRepository()
        assert await mostrar_metricas(repo, dias=30) == 0
        assert "No hay métricas registradas" in capsys.readouterr().out

    async def test_con_metricas_imprime_resumen_y_serie(self, capsys):
        from datetime import date
        from app.domain.entities.ranking_telemetry import RankingMetricDaily
        from tests.unit.application.fakes import InMemoryRankingTelemetryRepository
        from scripts.ranking_telemetry import mostrar_metricas

        repo = InMemoryRankingTelemetryRepository()
        await repo.upsert_daily_metric(
            RankingMetricDaily(
                day=date.today(),
                model_version="v1.0",
                ndcg_at_10=0.145,
                ci_low=0.12,
                ci_high=0.17,
                rankings_evaluated=20,
                rankings_served=100,
            )
        )

        assert await mostrar_metricas(repo, dias=30) == 0
        salida = capsys.readouterr().out
        assert "v1.0" in salida
        assert "0.1450" in salida
        assert "RESUMEN DE TELEMETRÍA" in salida
        assert "SERIE TEMPORAL DETALLADA" in salida
