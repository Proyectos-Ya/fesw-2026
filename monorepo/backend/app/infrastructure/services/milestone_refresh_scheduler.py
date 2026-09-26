"""Loop de detección de cambios de fecha en licitaciones sincronizadas (HU-16).

Mismo enfoque que los schedulers de ingesta y alertas: una tarea asyncio en el
lifespan, que asume una sola instancia de la API.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class MilestoneRefreshScheduler:
    def __init__(self, refresh: Callable[[], Awaitable[int]], interval_seconds: int):
        self.refresh = refresh
        self.interval_seconds = interval_seconds

    async def start_loop(self) -> None:
        logger.info("Revisando cambios de fechas cada %s segundos", self.interval_seconds)
        while True:
            try:
                cambiadas = await self.refresh()
                if cambiadas:
                    logger.info("%s licitaciones sincronizadas cambiaron de fecha", cambiadas)
            except Exception as error:
                # Un fallo no puede matar el loop: la próxima vuelta lo reintenta.
                logger.warning("Error al revisar cambios de fechas: %s", error)
            await asyncio.sleep(self.interval_seconds)
