"""Contar una ventana sin descargarla.

La volumetría necesita saber cuántas licitaciones hay en un día, no cuáles. El
listado ya entrega `paginacion.total_resultados` en la primera página, así que
la respuesta cuesta **una** petición: una serie de 30 días son 30 peticiones de
las 10.000 del ticket, frente a las ~30.000 que costaría listarlas.

Lo que más importa de estos tests es la distinción entre `0` y `None`. Un 0
significa "ese día no se publicó nada"; un None, "no se pudo saber". Devolver 0
ante una caída de la API metería un día falso en la serie, y una serie temporal
no perdona eso.
"""

from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.infrastructure.services.tenders.mercado_publico_client import (
    MercadoPublicoClient,
)

URL = "https://api2.mercadopublico.cl/v2/compra-agil"
DESDE = datetime(2026, 8, 1, tzinfo=UTC)
HASTA = datetime(2026, 8, 2, tzinfo=UTC)


def _con_total(total) -> httpx.Response:
    return httpx.Response(
        200, json={"payload": {"items": [], "paginacion": {"total_resultados": total}}}
    )


def _cliente() -> MercadoPublicoClient:
    return MercadoPublicoClient(api_key="t", espera_base=0)


async def _contar(respuesta: httpx.Response, **extra):
    respx.get(URL).mock(return_value=respuesta)
    return await _cliente().contar(DESDE, HASTA, **extra)


class TestElNumero:
    @respx.mock
    @pytest.mark.asyncio
    async def test_devuelve_el_total_que_reporta_la_api(self):
        assert await _contar(_con_total(437)) == 437

    @respx.mock
    @pytest.mark.asyncio
    async def test_cuesta_una_sola_peticion(self):
        """El total viene en la primera página: no hay que paginar para contar."""
        ruta = respx.get(URL).mock(return_value=_con_total(437))

        await _cliente().contar(DESDE, HASTA)

        assert ruta.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_cero_es_un_dato_y_no_una_falla(self):
        """Ese día no se publicó nada. Distinto de no haber podido preguntar."""
        assert await _contar(_con_total(0)) == 0


class TestCuandoNoSePudoSaber:
    """Todos estos casos devuelven None, nunca 0."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_sin_el_campo_en_la_respuesta(self):
        assert (
            await _contar(httpx.Response(200, json={"payload": {"items": []}})) is None
        )

    @respx.mock
    @pytest.mark.asyncio
    async def test_respuesta_ilegible(self):
        assert (
            await _contar(httpx.Response(200, content=b"<html>no json</html>")) is None
        )

    @respx.mock
    @pytest.mark.asyncio
    async def test_el_servidor_no_responde_tras_los_reintentos(self):
        assert await _contar(httpx.Response(504)) is None

    @respx.mock
    @pytest.mark.asyncio
    async def test_cuota_agotada(self):
        """Un 429 que sobrevive a los reintentos tampoco es un cero."""
        assert await _contar(httpx.Response(429)) is None

    @respx.mock
    @pytest.mark.asyncio
    async def test_total_no_numerico(self):
        assert await _contar(_con_total("muchas")) is None


class TestMismaVentanaQueLaIngesta:
    """El conteo y el listado comparten `_params_ventana` a propósito.

    Si divergieran, la volumetría mediría una ventana distinta de la que la
    ingesta consulta, y el informe estaría describiendo otro sistema.
    """

    @respx.mock
    @pytest.mark.asyncio
    async def test_por_defecto_pregunta_por_cambios(self):
        ruta = respx.get(URL).mock(return_value=_con_total(1))

        await _cliente().contar(DESDE, HASTA)

        params = dict(httpx.URL(str(ruta.calls.last.request.url)).params)
        assert params["ttl_cambio_ms"] == str(24 * 3600 * 1000)
        assert "publicado_desde" not in params

    @respx.mock
    @pytest.mark.asyncio
    async def test_por_publicacion_manda_el_rango_y_excluye_ttl(self):
        ruta = respx.get(URL).mock(return_value=_con_total(1))

        await _cliente().contar(DESDE, HASTA, por_publicacion=True)

        params = dict(httpx.URL(str(ruta.calls.last.request.url)).params)
        assert params["publicado_desde"] == "2026-08-01T00:00:00Z"
        assert params["publicado_hasta"] == "2026-08-02T00:00:00Z"
        assert "ttl_cambio_ms" not in params

    @respx.mock
    @pytest.mark.asyncio
    async def test_el_estado_viaja_al_servidor(self):
        ruta = respx.get(URL).mock(return_value=_con_total(1))

        await _cliente().contar(DESDE, HASTA, estado="cerrada,desierta")

        params = dict(httpx.URL(str(ruta.calls.last.request.url)).params)
        assert params["estado"] == "cerrada,desierta"

    @respx.mock
    @pytest.mark.asyncio
    async def test_manda_el_ticket_en_la_cabecera(self):
        ruta = respx.get(URL).mock(return_value=_con_total(1))

        await _cliente().contar(DESDE, HASTA)

        assert ruta.calls.last.request.headers["ticket"] == "t"
