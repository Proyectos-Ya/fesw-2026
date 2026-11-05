"""Ubica en el mapa las direcciones de entrega pendientes (HU-22, #314).

Lo corre el scheduler de geocodificación, nunca una petición del usuario: el
mapa solo lee lo que esto dejó guardado.
"""

import logging
from dataclasses import dataclass

from app.application.repositories.tender_geocoding_repository import (
    ITenderGeocodingRepository,
)
from app.application.services.geocoding_service import IGeocodingService
from app.domain.entities.tender_map import GeoPoint, GeoPrecision, PendingGeocoding
from app.domain.errors.geocoding_errors import GeocodingUnavailable

logger = logging.getLogger(__name__)


@dataclass
class GeocodingRun:
    """Lo que dejó una vuelta de la cola.

    `consultas` son las que salieron a la red y gastan cuota de Nominatim;
    `cacheadas`, las que resolvió `geocoding_cache` sin salir. La proporción
    entre las dos es lo que dice si la instancia pública alcanza.
    """

    ubicadas: int = 0
    consultas: int = 0
    cacheadas: int = 0


def geocoding_query(
    address: str | None, commune: str | None, region: str | None
) -> str:
    """La consulta que se manda y la clave de la caché: las partes presentes y "Chile".

    Los espacios se normalizan para que la misma dirección escrita con espacios
    de más caiga en la misma fila de la caché.
    """
    partes = [
        " ".join(p.split()) for p in (address, commune, region) if p and p.strip()
    ]
    return ", ".join([*partes, "Chile"])


class GeocodePendingTendersUseCase:
    def __init__(
        self,
        repo: ITenderGeocodingRepository,
        geocoder: IGeocodingService,
        batch_size: int,
    ) -> None:
        self.repo = repo
        self.geocoder = geocoder
        self.batch_size = batch_size

    async def execute(self) -> GeocodingRun:
        """Procesa un lote y cuenta qué pasó con él.

        Si el servicio se cae, corta el lote: lo que falta sigue pendiente y la
        vuelta siguiente lo retoma. Insistir solo gastaría la cuota.
        """
        run = GeocodingRun()
        for pendiente in await self.repo.list_pending(self.batch_size):
            try:
                punto, precision = await self._ubicar(pendiente, run)
            except GeocodingUnavailable as exc:
                logger.warning("Geocodificación interrumpida: %s", exc)
                break
            await self.repo.save_location(pendiente.tender_id, punto, precision)
            run.ubicadas += 1
        return run

    async def _ubicar(
        self, pendiente: PendingGeocoding, run: GeocodingRun
    ) -> tuple[GeoPoint | None, GeoPrecision]:
        direccion = geocoding_query(
            pendiente.delivery_address, pendiente.commune, pendiente.region
        )
        punto = await self._consultar(direccion, run)
        if punto is not None:
            return punto, GeoPrecision.DIRECCION

        # La región sola no es un punto de entrega: sin comuna no hay respaldo.
        if pendiente.commune:
            punto = await self._consultar(
                geocoding_query(None, pendiente.commune, pendiente.region), run
            )
            if punto is not None:
                return punto, GeoPrecision.COMUNA

        return None, GeoPrecision.NO_ENCONTRADA

    async def _consultar(self, query: str, run: GeocodingRun) -> GeoPoint | None:
        guardada = await self.repo.get_cached(query)
        if guardada is not None:
            run.cacheadas += 1
            return guardada.point
        # El contador va después de la llamada: una que se cayó no gastó cuota.
        punto = await self.geocoder.geocode(query)
        run.consultas += 1
        await self.repo.cache(query, punto)
        return punto
