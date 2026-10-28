"""Geocodificación con Nominatim, el buscador de direcciones de OpenStreetMap (#314).

Sin key ni costo, con dos condiciones de su política de uso
(https://operations.osmfoundation.org/policies/nominatim/): identificar la
aplicación en el `User-Agent` y no pasar de una petición por segundo. Lo
segundo lo respeta el scheduler, que es el único que llama a este cliente.

Sin reintentos: una caída deja la licitación pendiente y la vuelta siguiente
la vuelve a intentar.
"""

import json
import logging
from typing import Any

import httpx
from pydantic import ValidationError

from app.application.services.geocoding_service import IGeocodingService
from app.domain.entities.tender_map import GeoPoint
from app.domain.errors.geocoding_errors import GeocodingUnavailable

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://nominatim.openstreetmap.org"
DEFAULT_TIMEOUT_SECONDS = 10.0


class NominatimGeocodingService(IGeocodingService):
    def __init__(
        self,
        contact_email: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._headers = {
            "Accept": "application/json",
            "User-Agent": f"Chiripa/1.0 ({contact_email})",
        }

    async def geocode(self, query: str) -> GeoPoint | None:
        params = {"q": query, "format": "jsonv2", "countrycodes": "cl", "limit": "1"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._base_url}/search", params=params, headers=self._headers
                )
        except httpx.TransportError as exc:
            logger.warning("Nominatim no respondió: %s", exc)
            raise GeocodingUnavailable(str(exc)) from exc

        if response.status_code >= 400:
            # 429 es que nos pasamos del límite: tampoco es "no encontrado".
            logger.warning("Nominatim respondió %s", response.status_code)
            raise GeocodingUnavailable(f"HTTP {response.status_code}")

        try:
            payload = json.loads(response.content)
        except ValueError as exc:
            logger.warning("Nominatim no respondió JSON válido")
            raise GeocodingUnavailable("JSON inválido") from exc

        return _primer_punto(payload)


def _primer_punto(payload: Any) -> GeoPoint | None:
    """El primer lugar de la lista, o `None` si no hay uno legible."""
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
        return None
    lugar = payload[0]
    try:
        return GeoPoint(lat=float(lugar["lat"]), lng=float(lugar["lon"]))
    except (KeyError, TypeError, ValueError, ValidationError):
        logger.info("Nominatim devolvió un lugar ilegible: %r", lugar)
        return None
