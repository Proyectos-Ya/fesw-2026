"""Rotación de tickets cuando uno agota su cuota.

La cuota de 10.000 peticiones al día es del **ticket**, no de la máquina ni del
proyecto, así que varios tickets suman capacidad. Lo que se prueba acá es
*cuándo* se rota, que es la parte que se puede hacer mal de dos formas opuestas:

- Rotar demasiado pronto —repartiendo las peticiones entre todos— gastaría los
  tickets en paralelo y dejaría la ingesta sin margen justo al final.
- No rotar nunca deja capacidad sin usar y corta la corrida a mitad.

La regla es rotar **por agotamiento**: recién cuando un 429 sobrevive a los
cuatro reintentos. La API devuelve 429 por dos motivos que no distingue —un balde
de tokens que se recarga en segundos, y la cuota del día—, y esperar al final
acierta en los dos.
"""

from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.infrastructure.services.tenders.mercado_publico_client import (
    CuotaAgotadaError,
    MercadoPublicoClient,
)

URL = "https://api2.mercadopublico.cl/v2/compra-agil"
DETALLE = f"{URL}/1234-56-COT26"
DESDE = datetime(2026, 8, 1, tzinfo=UTC)
HASTA = datetime(2026, 8, 2, tzinfo=UTC)

# Cuatro intentos por ticket: es lo que hace el cliente antes de darlo por agotado.
INTENTOS_POR_TICKET = 4


def _cliente(*tickets: str) -> MercadoPublicoClient:
    return MercadoPublicoClient(api_keys=list(tickets), espera_base=0)


def _ok_total(total: int = 7) -> httpx.Response:
    return httpx.Response(
        200, json={"payload": {"items": [], "paginacion": {"total_resultados": total}}}
    )


def _429() -> httpx.Response:
    return httpx.Response(429, json={"errors": []})


def _tickets_usados(ruta) -> list[str]:
    return [c.request.headers["ticket"] for c in ruta.calls]


class TestConstruccion:
    def test_un_solo_ticket_sigue_funcionando_igual(self):
        """Los seis sitios que construyen el cliente pasan `api_key` a secas."""
        cliente = MercadoPublicoClient(api_key="uno", espera_base=0)

        assert cliente.api_key == "uno"

    def test_api_key_refleja_el_ticket_en_uso(self):
        cliente = _cliente("uno", "dos")

        assert cliente.api_key == "uno"
        assert cliente._rotar_ticket() is True
        assert cliente.api_key == "dos"

    def test_no_rota_mas_alla_del_ultimo(self):
        """Un ticket agotado no se recupera dentro de la misma corrida."""
        cliente = _cliente("uno", "dos")
        cliente._rotar_ticket()

        assert cliente._rotar_ticket() is False
        assert cliente.api_key == "dos"

    def test_sin_ningun_ticket_no_se_construye(self):
        with pytest.raises(ValueError):
            MercadoPublicoClient(api_keys=[])


class TestListado:
    @respx.mock
    @pytest.mark.asyncio
    async def test_rota_cuando_el_primero_agota_su_cuota(self):
        ruta = respx.get(URL).mock(
            side_effect=[*[_429()] * INTENTOS_POR_TICKET, _ok_total(437)]
        )

        total = await _cliente("uno", "dos").contar(DESDE, HASTA)

        assert total == 437
        assert _tickets_usados(ruta)[-1] == "dos"

    @respx.mock
    @pytest.mark.asyncio
    async def test_agota_el_primero_antes_de_tocar_el_segundo(self):
        """No reparte: quema uno entero y recién ahí cambia."""
        ruta = respx.get(URL).mock(
            side_effect=[*[_429()] * INTENTOS_POR_TICKET, _ok_total()]
        )

        await _cliente("uno", "dos").contar(DESDE, HASTA)

        usados = _tickets_usados(ruta)
        assert usados[:INTENTOS_POR_TICKET] == ["uno"] * INTENTOS_POR_TICKET
        assert usados[INTENTOS_POR_TICKET] == "dos"

    @respx.mock
    @pytest.mark.asyncio
    async def test_con_todos_agotados_devuelve_el_429(self):
        respx.get(URL).mock(return_value=_429())

        assert await _cliente("uno", "dos").contar(DESDE, HASTA) is None

    @respx.mock
    @pytest.mark.asyncio
    async def test_un_429_pasajero_no_gasta_un_ticket(self):
        """Se reintenta con el mismo: el balde de tokens se recarga en segundos."""
        ruta = respx.get(URL).mock(side_effect=[_429(), _ok_total(12)])

        total = await _cliente("uno", "dos").contar(DESDE, HASTA)

        assert total == 12
        assert _tickets_usados(ruta) == ["uno", "uno"]

    @respx.mock
    @pytest.mark.asyncio
    async def test_un_5xx_no_rota(self):
        """Que el servidor falle no dice nada sobre la cuota del ticket."""
        ruta = respx.get(URL).mock(return_value=httpx.Response(504))

        await _cliente("uno", "dos").contar(DESDE, HASTA)

        assert set(_tickets_usados(ruta)) == {"uno"}


class TestDetalle:
    @respx.mock
    @pytest.mark.asyncio
    async def test_rota_cuando_el_primero_agota_su_cuota(self):
        ruta = respx.get(DETALLE).mock(
            side_effect=[
                *[_429()] * INTENTOS_POR_TICKET,
                httpx.Response(200, json={"payload": {"codigo": "1234-56-COT26"}}),
            ]
        )

        detalle = await _cliente("uno", "dos").get_tender_detail("1234-56-COT26")

        assert detalle == {"codigo": "1234-56-COT26"}
        assert _tickets_usados(ruta)[-1] == "dos"

    @respx.mock
    @pytest.mark.asyncio
    async def test_con_todos_agotados_levanta_cuota_agotada(self):
        """Mientras quede un ticket, el fallo del anterior es invisible para la
        ingesta; recién cuando no queda ninguno se le avisa."""
        respx.get(DETALLE).mock(return_value=_429())

        with pytest.raises(CuotaAgotadaError):
            await _cliente("uno", "dos").get_tender_detail("1234-56-COT26")

    @respx.mock
    @pytest.mark.asyncio
    async def test_con_un_solo_ticket_el_comportamiento_no_cambia(self):
        respx.get(DETALLE).mock(return_value=_429())

        with pytest.raises(CuotaAgotadaError):
            await MercadoPublicoClient(api_key="uno", espera_base=0).get_tender_detail(
                "1234-56-COT26"
            )
