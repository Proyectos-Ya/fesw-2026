"""Loop de la cola de geocodificación de las direcciones de entrega (HU-22, #314).

Mismo enfoque que los demás schedulers: una tarea asyncio en el lifespan, que
asume una sola instancia de la API. Con dos, Nominatim recibiría el doble de
peticiones.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class GeocodingScheduler:
    def __init__(
        self,
        geocode: Callable[[], Awaitable[int]],
        interval_seconds: int,
        batch_size: int | None = None,
    ):
        self.geocode = geocode
        self.interval_seconds = interval_seconds
        self.batch_size = batch_size

    async def start_loop(self) -> None:
        logger.info(
            "Geocodificando direcciones de entrega cada %s segundos",
            self.interval_seconds,
        )
        while True:
            guardadas = 0
            try:
                guardadas = await self.geocode()
                if guardadas:
                    logger.info("%s licitaciones ubicadas en el mapa", guardadas)
            except Exception as error:
                # Un fallo no puede matar el loop: la próxima vuelta lo reintenta.
                logger.warning(
                    "Error al geocodificar direcciones de entrega: %s", error
                )
            # Un lote lleno indica que queda cola: se sigue sin esperar el
            # intervalo, porque el ritmo ya lo limita el servicio (1 req/s).
            if self.batch_size and guardadas >= self.batch_size:
                await asyncio.sleep(0)
                continue
            await asyncio.sleep(self.interval_seconds)
