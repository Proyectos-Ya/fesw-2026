"""Cliente de Nominatim (OpenStreetMap) para ubicar direcciones de entrega (#314).

No toca la red: `respx` intercepta httpx. El payload reproduce la forma de
`/search?format=jsonv2`: una lista de lugares con `lat` y `lon` como texto.
"""

import httpx
import pytest
import respx

from app.domain.entities.tender_map import GeoPoint
from app.domain.errors.geocoding_errors import GeocodingUnavailable
from app.infrastructure.services.geocoding.nominatim_geocoding_service import (
    NominatimGeocodingService,
)

BASE = "https://nominatim.example.org"
URL = f"{BASE}/search"
CORREO = "equipo@example.org"


def _servicio() -> NominatimGeocodingService:
    return NominatimGeocodingService(contact_email=CORREO, base_url=BASE)


@respx.mock
async def test_devuelve_el_primer_lugar_como_punto():
    respx.get(URL).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "place_id": 1,
                    "lat": "-41.8697",
                    "lon": "-73.8203",
                    "display_name": "Yerbas Buenas 915, Ancud, Los Lagos, Chile",
                }
            ],
        )
    )

    punto = await _servicio().geocode("Yerbas Buenas #915, Ancud, Los Lagos, Chile")

    assert punto == GeoPoint(lat=-41.8697, lng=-73.8203)


@respx.mock
async def test_manda_la_consulta_restringida_a_chile_y_se_identifica():
    ruta = respx.get(URL).mock(return_value=httpx.Response(200, json=[]))

    await _servicio().geocode("Ramón Freire 5, Coyhaique, Aysén, Chile")

    peticion = ruta.calls.last.request
    assert peticion.url.params["q"] == "Ramón Freire 5, Coyhaique, Aysén, Chile"
    assert peticion.url.params["countrycodes"] == "cl"
    assert peticion.url.params["format"] == "jsonv2"
    assert peticion.url.params["limit"] == "1"
    # La política de uso de Nominatim exige identificar la aplicación.
    assert CORREO in peticion.headers["User-Agent"]


@respx.mock
async def test_sin_resultados_es_none():
    respx.get(URL).mock(return_value=httpx.Response(200, json=[]))

    assert await _servicio().geocode("Calle que no existe 0, Chile") is None


@respx.mock
async def test_con_api_key_manda_key_y_404_es_sin_resultados():
    ruta = respx.get("https://us1.locationiq.com/v1/search").mock(
        return_value=httpx.Response(404, json={"error": "Unable to geocode"})
    )
    servicio = NominatimGeocodingService(
        api_key="pk.test_123", base_url="https://us1.locationiq.com/v1"
    )

    assert await servicio.geocode("Calle Sin Numero, Chile") is None
    peticion = ruta.calls.last.request
    assert peticion.url.params["key"] == "pk.test_123"
    assert peticion.url.params["format"] == "json"


@pytest.mark.parametrize(
    "payload",
    [
        {"error": "algo"},
        [{"lat": "no-es-numero", "lon": "-70.6"}],
        [{"lon": "-70.6"}],
        [{"lat": "95", "lon": "-70.6"}],
        ["texto"],
    ],
)
@respx.mock
async def test_una_respuesta_rara_es_none(payload):
    respx.get(URL).mock(return_value=httpx.Response(200, json=payload))

    assert await _servicio().geocode("Algo, Chile") is None


@respx.mock
async def test_una_consulta_rechazada_con_400_es_sin_resultados():
    """Direcciones con horarios y teléfonos pasan el largo máximo del proveedor.

    El 400 es de esa consulta, no del servicio: si cortara el lote, la cola
    quedaría trabada para siempre en esa licitación.
    """
    respx.get(URL).mock(return_value=httpx.Response(400, json={"error": "Invalid"}))

    assert await _servicio().geocode("x" * 300) is None


@pytest.mark.parametrize("codigo", [401, 403, 429, 500, 503])
@respx.mock
async def test_un_error_del_servidor_es_no_disponible(codigo):
    respx.get(URL).mock(return_value=httpx.Response(codigo))

    with pytest.raises(GeocodingUnavailable):
        await _servicio().geocode("Algo, Chile")


@respx.mock
async def test_json_invalido_es_no_disponible():
    respx.get(URL).mock(return_value=httpx.Response(200, content=b"<html>"))

    with pytest.raises(GeocodingUnavailable):
        await _servicio().geocode("Algo, Chile")


@respx.mock
async def test_un_error_de_red_es_no_disponible():
    respx.get(URL).mock(side_effect=httpx.ConnectError("sin red"))

    with pytest.raises(GeocodingUnavailable):
        await _servicio().geocode("Algo, Chile")
