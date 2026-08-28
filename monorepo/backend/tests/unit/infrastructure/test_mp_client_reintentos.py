"""Un 429 pasajero no debe abortar la sincronización.

El cliente trataba el 429 como terminal, siguiendo la guía de la API, que manda
esperar al día siguiente. **Medido el 28 de agosto de 2026, eso no se sostiene**:
la API aplica un balde de tokens de capacidad pequeña que se recarga en
segundos. En una serie de pruebas aparecieron 429 sueltos entre respuestas
correctas, y una petición inmediatamente posterior devolvía 200.

Con el comportamiento anterior, un 429 de esos detenía la paginación entera. En
la sincronización diaria se nota poco —se retoma al día siguiente—, pero una
carga inicial de horas no llegaría nunca al final.
"""

import httpx
import pytest
import respx

from app.infrastructure.services.tenders.mercado_publico_client import (
    MercadoPublicoClient,
)

URL = "https://api2.mercadopublico.cl/v2/compra-agil"


def _cliente() -> MercadoPublicoClient:
    # espera_base=0 para no dormir de verdad en los tests.
    return MercadoPublicoClient(api_key="ticket-de-prueba", espera_base=0)


async def _pedir(cliente: MercadoPublicoClient) -> httpx.Response | None:
    async with httpx.AsyncClient() as c:
        return await cliente._get_con_reintentos(c, {"ticket": "x"}, {"p": 1})


class TestReintentoDel429:
    @respx.mock
    @pytest.mark.asyncio
    async def test_un_429_pasajero_se_reintenta_y_sigue(self):
        ruta = respx.get(URL).mock(
            side_effect=[
                httpx.Response(429, json={"errors": []}),
                httpx.Response(200, json={"payload": {"items": []}}),
            ]
        )

        respuesta = await _pedir(_cliente())

        assert respuesta is not None
        assert respuesta.status_code == 200
        assert ruta.call_count == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_un_429_persistente_se_devuelve_para_que_el_llamador_corte(self):
        """Si insiste, la cuota sí se agotó y hay que parar de verdad."""
        respx.get(URL).mock(return_value=httpx.Response(429, json={"errors": []}))

        respuesta = await _pedir(_cliente())

        assert respuesta is not None
        assert respuesta.status_code == 429


class TestLoQueYaFuncionaba:
    @respx.mock
    @pytest.mark.asyncio
    async def test_un_504_pasajero_se_reintenta(self):
        respx.get(URL).mock(
            side_effect=[
                httpx.Response(504),
                httpx.Response(200, json={"payload": {"items": []}}),
            ]
        )

        assert (await _pedir(_cliente())).status_code == 200

    @respx.mock
    @pytest.mark.asyncio
    async def test_un_400_no_se_reintenta(self):
        """Un error de parámetros no mejora insistiendo."""
        ruta = respx.get(URL).mock(return_value=httpx.Response(400))

        respuesta = await _pedir(_cliente())

        assert respuesta.status_code == 400
        assert ruta.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_si_nunca_responde_devuelve_none(self):
        respx.get(URL).mock(side_effect=httpx.TimeoutException("agotado"))

        assert await _pedir(_cliente()) is None
