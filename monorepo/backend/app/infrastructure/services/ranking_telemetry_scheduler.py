"""Bucle de la telemetría del ranking (plan 233, decisión 8).

Mismo enfoque que `MilestoneRefreshScheduler`: una tarea asyncio en el lifespan,
que asume una sola instancia de la API. Con dos, el trabajo sigue siendo
idempotente (upserts y purga) y solo se duplica algún snapshot.

**Por qué un bucle y no un cron de Railway:** Config as Code de Railway caduca el
2026-12-01, un servicio nuevo hay que configurarlo a mano en el panel, y el
trabajo es SQL liviano sobre tablas propias. El mismo ciclo corre a mano con
`scripts/ranking_telemetry.py` (backfill o QA).
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from app.application.use_cases.ranking_telemetry.run_ranking_telemetry_cycle import (
    RankingTelemetryCycleResult,
)

logger = logging.getLogger(__name__)


class RankingTelemetryScheduler:
    def __init__(
        self,
        run_cycle: Callable[[], Awaitable[RankingTelemetryCycleResult]],
        interval_seconds: int,
        initial_delay_seconds: int = 300,
    ):
        self.run_cycle = run_cycle
        self.interval_seconds = interval_seconds
        self.initial_delay_seconds = initial_delay_seconds

    async def start_loop(self) -> None:
        logger.info(
            "Calculando la telemetría del ranking cada %s segundos",
            self.interval_seconds,
        )
        # No compite con el arranque: la API recién levanta Qdrant y los modelos.
        await asyncio.sleep(self.initial_delay_seconds)
        while True:
            try:
                resultado = await self.run_cycle()
                if resultado.failures:
                    logger.warning(
                        "Telemetría del ranking con fallos: %s",
                        "; ".join(resultado.failures),
                    )
            except Exception as error:
                # Un fallo no puede matar el loop: la próxima vuelta lo reintenta.
                logger.warning("Error en la telemetría del ranking: %s", error)
            await asyncio.sleep(self.interval_seconds)
