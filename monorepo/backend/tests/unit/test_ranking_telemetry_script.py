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
