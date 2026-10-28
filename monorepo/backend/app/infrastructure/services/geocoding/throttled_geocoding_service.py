"""Límite de ritmo de Nominatim: una petición por segundo como máximo (#314).

Envuelve al cliente real. Los aciertos de la caché ni siquiera llegan acá, así
que no esperan.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable

from app.application.services.geocoding_service import IGeocodingService
from app.domain.entities.tender_map import GeoPoint


class ThrottledGeocodingService(IGeocodingService):
    def __init__(
        self,
        inner: IGeocodingService,
        min_interval_seconds: float = 1.0,
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
