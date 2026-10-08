"""Loop de auto-archivado del tablero Kanban (HdU 10, CA4).

Mismo patrón que `MilestoneRefreshScheduler` y `NotificationScheduler`: una
tarea asyncio en el lifespan de FastAPI, con la hipótesis de que corre una
sola instancia. Si en algún momento hay dos réplicas, el peor caso es que
las dos actualicen las mismas filas con el mismo valor; no corrompe datos.

Frecuencia: diaria. El reloj real que importa son los 90 días del
`board_entered_at`; una pasada por día es más que suficiente para no dejar
tarjetas colgadas visiblemente más allá del corte.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 60 * 60 * 24  # 24 h


class KanbanArchiveScheduler:
    def __init__(
        self,
        auto_archive: Callable[[], Awaitable[list[UUID]]],
        interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    ) -> None:
        self.auto_archive = auto_archive
        self.interval_seconds = interval_seconds

    async def start_loop(self) -> None:
        logger.info(
            "[Kanban] Loop de auto-archivado activo (cada %s segundos)",
            self.interval_seconds,
        )
        while True:
            try:
                archived = await self.auto_archive()
                if archived:
                    logger.info(
                        "[Kanban] %s tarjetas auto-archivadas por inactividad",
                        len(archived),
                    )
            except Exception as error:
                # Un fallo puntual no puede matar el bucle: la siguiente
                # vuelta reintentará.
                logger.warning("[Kanban] Error en el auto-archivado: %s", error)
            await asyncio.sleep(self.interval_seconds)
