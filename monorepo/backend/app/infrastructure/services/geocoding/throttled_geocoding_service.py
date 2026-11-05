"""Límite de ritmo de las consultas a Nominatim (#314).

Envuelve al cliente real. Los aciertos de la caché ni siquiera llegan acá, así
que no esperan.

El máximo de una petición por segundo que encabeza la política de uso
(https://operations.osmfoundation.org/policies/nominatim/) es para uso
interactivo. Un proceso que consulta a intervalos regulares y corre más de un
día —como el scheduler de la cola— cae en el otro tramo de esa misma política,
que permite **4 peticiones por minuto**. Pasarse de ahí hace que bloqueen al
proyecto, y el bloqueo no se nota: el mapa simplemente deja de sumar marcadores.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable

from app.application.services.geocoding_service import IGeocodingService
from app.domain.entities.tender_map import GeoPoint

# 4 peticiones por minuto, el tramo de la política para un proceso permanente.
NOMINATIM_MIN_INTERVAL_SECONDS = 15.0


class ThrottledGeocodingService(IGeocodingService):
    def __init__(
        self,
        inner: IGeocodingService,
        min_interval_seconds: float = NOMINATIM_MIN_INTERVAL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._inner = inner
        self._min_interval = min_interval_seconds
        self._clock = clock
        self._sleep = sleep
        self._ultima: float | None = None

    async def geocode(self, query: str) -> GeoPoint | None:
        if self._ultima is not None:
            falta = self._min_interval - (self._clock() - self._ultima)
            if falta > 0:
                await self._sleep(falta)
        try:
            return await self._inner.geocode(query)
        finally:
            # También tras un error: una caída no habilita a insistir más rápido.
            self._ultima = self._clock()
