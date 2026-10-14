import asyncio
import logging

from app.application.use_cases.ranking_telemetry.run_ranking_telemetry_cycle import (
    RankingTelemetryCycleResult,
)
from app.infrastructure.services.ranking_telemetry_scheduler import (
    RankingTelemetryScheduler,
)


class TestScheduler:
    async def test_un_error_no_detiene_el_loop(self):
        llamadas = 0

        async def ciclo() -> RankingTelemetryCycleResult:
            nonlocal llamadas
            llamadas += 1
            if llamadas == 1:
                raise RuntimeError("base caída")
            return RankingTelemetryCycleResult()

        tarea = asyncio.create_task(
            RankingTelemetryScheduler(
                ciclo, interval_seconds=0, initial_delay_seconds=0
            ).start_loop()
        )
        while llamadas < 3:
            await asyncio.sleep(0)
        tarea.cancel()

        assert llamadas >= 3

    async def test_espera_el_retraso_inicial_antes_del_primer_ciclo(self):
        llamadas = 0

        async def ciclo() -> RankingTelemetryCycleResult:
            nonlocal llamadas
            llamadas += 1
            return RankingTelemetryCycleResult()

        tarea = asyncio.create_task(
            RankingTelemetryScheduler(
                ciclo, interval_seconds=3600, initial_delay_seconds=3600
            ).start_loop()
        )
        for _ in range(5):
            await asyncio.sleep(0)
        tarea.cancel()

        assert llamadas == 0

    async def test_deja_un_aviso_si_algun_trabajo_del_ciclo_fallo(self, caplog):
        llamadas = 0

        async def ciclo() -> RankingTelemetryCycleResult:
            nonlocal llamadas
            llamadas += 1
            return RankingTelemetryCycleResult(failures=("prioridad: boom",))

        with caplog.at_level(logging.WARNING):
            tarea = asyncio.create_task(
                RankingTelemetryScheduler(
                    ciclo, interval_seconds=0, initial_delay_seconds=0
                ).start_loop()
            )
            while llamadas < 1:
                await asyncio.sleep(0)
            tarea.cancel()

        assert "prioridad: boom" in caplog.text
