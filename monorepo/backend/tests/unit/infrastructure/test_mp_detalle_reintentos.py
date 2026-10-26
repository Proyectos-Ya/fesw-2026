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


class TestCuotaConConteoPropio:
    """El 429 tiene su propio conteo, independiente de `intentos_detalle`.

    El 2026-10-14, con 2 intentos de detalle en las corridas frecuentes y 3 en
    la nocturna, una ráfaga corta de 429 (el balde de tokens de la API, que se
    recarga en segundos) alcanzaba para declarar la cuota agotada: la nocturna
    se cortó con 1.585 pendientes, la frecuente de las 14:02 con 903 y la de las
    20:02 no procesó nada. Con 2 tickets y ~12.350 peticiones en el día, la
    cuota real alcanzaba.
    """

    @respx.mock
    @pytest.mark.asyncio
    async def test_una_rafaga_de_429_no_agota_con_pocos_intentos(self):
        respx.get(URL).mock(
            side_effect=[
                httpx.Response(429),
                httpx.Response(429),
                httpx.Response(429),
                httpx.Response(200, json={"payload": {"codigo": "LIC-1"}}),
            ]
        )
        cliente = MercadoPublicoClient(api_key="t", espera_base=0, intentos_detalle=1)

        assert await cliente.get_tender_detail("LIC-1") == {"codigo": "LIC-1"}

    @respx.mock
    @pytest.mark.asyncio
    async def test_un_429_persistente_agota_tras_su_propio_conteo(self):
        ruta = respx.get(URL).mock(return_value=httpx.Response(429))
        cliente = MercadoPublicoClient(api_key="t", espera_base=0, intentos_detalle=1)

        with pytest.raises(CuotaAgotadaError):
            await cliente.get_tender_detail("LIC-1")

        assert ruta.call_count == 4

    @respx.mock
    @pytest.mark.asyncio
    async def test_los_5xx_siguen_usando_intentos_detalle(self):
        ruta = respx.get(URL).mock(return_value=httpx.Response(504))
        cliente = MercadoPublicoClient(api_key="t", espera_base=0, intentos_detalle=2)

        with pytest.raises(ErrorTransitorioMercadoPublico):
            await cliente.get_tender_detail("LIC-1")

        assert ruta.call_count == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_429_y_504_mezclados_cuentan_por_separado(self):
        respx.get(URL).mock(
            side_effect=[
                httpx.Response(429),
                httpx.Response(504),
                httpx.Response(429),
                httpx.Response(200, json={"payload": {"codigo": "LIC-1"}}),
            ]
        )
        cliente = MercadoPublicoClient(api_key="t", espera_base=0, intentos_detalle=2)

        assert await cliente.get_tender_detail("LIC-1") == {"codigo": "LIC-1"}
