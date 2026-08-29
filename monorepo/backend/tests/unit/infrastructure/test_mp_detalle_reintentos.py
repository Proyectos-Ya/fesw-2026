"""El detalle también reintenta el 429 antes de darlo por cuota agotada.

Mismo hallazgo que en el listado: la API aplica un balde de tokens que se recarga
en segundos, así que los 429 aparecen sueltos entre respuestas correctas. Al
primero, `get_tender_detail` levantaba `CuotaAgotadaError` y el servicio cortaba
la ingesta completa. En una carga inicial de horas eso la detiene a los minutos.
"""

import httpx
import pytest
import respx

from app.infrastructure.services.tenders.mercado_publico_client import (
    CuotaAgotadaError,
    ErrorTransitorioMercadoPublico,
    MercadoPublicoClient,
)

URL = "https://api2.mercadopublico.cl/v2/compra-agil/LIC-1"


def _cliente() -> MercadoPublicoClient:
    return MercadoPublicoClient(api_key="t", espera_base=0)


class TestReintentoDelDetalle:
    @respx.mock
    @pytest.mark.asyncio
    async def test_un_429_pasajero_se_reintenta(self):
        respx.get(URL).mock(
            side_effect=[
                httpx.Response(429),
                httpx.Response(200, json={"payload": {"codigo": "LIC-1"}}),
            ]
        )

        assert await _cliente().get_tender_detail("LIC-1") == {"codigo": "LIC-1"}

    @respx.mock
    @pytest.mark.asyncio
    async def test_un_429_persistente_si_es_cuota_agotada(self):
        """Si insiste tras varios intentos, la cuota se agotó de verdad."""
        respx.get(URL).mock(return_value=httpx.Response(429))

        with pytest.raises(CuotaAgotadaError):
            await _cliente().get_tender_detail("LIC-1")

    @respx.mock
    @pytest.mark.asyncio
    async def test_un_5xx_pasajero_se_reintenta(self):
        respx.get(URL).mock(
            side_effect=[
                httpx.Response(500),
                httpx.Response(200, json={"payload": {"codigo": "LIC-1"}}),
            ]
        )

        assert await _cliente().get_tender_detail("LIC-1") == {"codigo": "LIC-1"}

    @respx.mock
    @pytest.mark.asyncio
    async def test_un_5xx_persistente_sigue_siendo_transitorio(self):
        """No marca la licitación como procesada: se reintenta en otra ronda."""
        respx.get(URL).mock(return_value=httpx.Response(503))

        with pytest.raises(ErrorTransitorioMercadoPublico):
            await _cliente().get_tender_detail("LIC-1")

    @respx.mock
    @pytest.mark.asyncio
    async def test_un_404_no_se_reintenta(self):
        """Esa licitación no está disponible; insistir solo gasta cuota.

        Devuelve `{}` y no levanta: la ingesta la marca procesada y no vuelve
        sobre ella, que es lo correcto para un 4xx.
        """
        ruta = respx.get(URL).mock(return_value=httpx.Response(404))

        assert await _cliente().get_tender_detail("LIC-1") == {}
        assert ruta.call_count == 1
