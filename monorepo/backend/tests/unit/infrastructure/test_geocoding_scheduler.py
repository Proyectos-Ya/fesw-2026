"""Scheduler de la cola de geocodificación y su límite de ritmo (HU-22, #314)."""

import asyncio

from app.application.services.geocoding_service import IGeocodingService
from app.application.use_cases.tender.geocode_pending_tenders import GeocodingRun
from app.domain.entities.tender_map import GeoPoint
from app.infrastructure.services.geocoding.geocoding_scheduler import (
    GeocodingScheduler,
)
from app.infrastructure.services.geocoding.throttled_geocoding_service import (
    ThrottledGeocodingService,
)


class TestScheduler:
    async def test_un_error_no_detiene_el_loop(self):
        llamadas = 0

        async def geocodificar() -> GeocodingRun:
            nonlocal llamadas
            llamadas += 1
            if llamadas == 1:
                raise RuntimeError("base caída")
            return GeocodingRun()

        tarea = asyncio.create_task(
            GeocodingScheduler(geocodificar, interval_seconds=0).start_loop()
        )
        while llamadas < 3:
            await asyncio.sleep(0)
        tarea.cancel()

        assert llamadas >= 3

    async def test_con_un_lote_lleno_sigue_sin_esperar_el_intervalo(self):
        """Mientras haya cola, cada vuelta procesa un lote completo seguido."""
        llamadas = 0

        async def geocodificar() -> GeocodingRun:
            nonlocal llamadas
            llamadas += 1
            return GeocodingRun(ubicadas=10) if llamadas < 3 else GeocodingRun()

        tarea = asyncio.create_task(
            GeocodingScheduler(
                geocodificar, interval_seconds=3600, batch_size=10
            ).start_loop()
        )
        for _ in range(20):
            await asyncio.sleep(0)
        tarea.cancel()

        # Dos lotes llenos y uno parcial; recién ahí espera la hora.
        assert llamadas == 3


class GeocoderFalso(IGeocodingService):
    def __init__(self) -> None:
        self.consultas: list[str] = []

    async def geocode(self, query: str) -> GeoPoint | None:
        self.consultas.append(query)
        return None


class RelojFalso:
    def __init__(self) -> None:
        self.ahora = 100.0
        self.esperas: list[float] = []

    def monotonic(self) -> float:
        return self.ahora

    async def sleep(self, segundos: float) -> None:
        self.esperas.append(segundos)
        self.ahora += segundos


class TestRitmo:
    def _servicio(self, reloj: RelojFalso, interno: GeocoderFalso):
        return ThrottledGeocodingService(
            interno, min_interval_seconds=1.0, clock=reloj.monotonic, sleep=reloj.sleep
        )

    async def test_la_primera_llamada_no_espera(self):
        reloj, interno = RelojFalso(), GeocoderFalso()

        await self._servicio(reloj, interno).geocode("a")

        assert reloj.esperas == []
        assert interno.consultas == ["a"]

    async def test_dos_seguidas_quedan_separadas_por_un_segundo(self):
        reloj, interno = RelojFalso(), GeocoderFalso()
        servicio = self._servicio(reloj, interno)

        await servicio.geocode("a")
        reloj.ahora += 0.25
        await servicio.geocode("b")

        assert reloj.esperas == [0.75]
        assert interno.consultas == ["a", "b"]

    async def test_si_ya_paso_el_segundo_no_espera(self):
        reloj, interno = RelojFalso(), GeocoderFalso()
        servicio = self._servicio(reloj, interno)

        await servicio.geocode("a")
        reloj.ahora += 3
        await servicio.geocode("b")

        assert reloj.esperas == []
