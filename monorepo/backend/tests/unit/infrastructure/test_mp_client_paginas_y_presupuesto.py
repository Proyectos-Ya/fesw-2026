"""Lo que el cliente de Mercado Público necesita para el plan 305.

- **Callback por página.** El cron de estados aplica cada página apenas llega.
  Antes aplicaba todo al terminar el listado, y una corrida que vencía el tope
  perdía lo que ya había listado.
- **Intentos de detalle configurables.** La ingesta frecuente pide menos
  intentos que la nocturna: cada intento contra un 504 es una petición gastada.
- **Contador y presupuesto.** Cada corrida registra cuántas peticiones hizo,
  reintentos incluidos, y se detiene al llegar a su máximo.
"""

import httpx
import pytest
import respx

from app.infrastructure.services.tenders.mercado_publico_client import (
    ErrorTransitorioMercadoPublico,
    MercadoPublicoClient,
    PresupuestoAgotadoError,
)
from app.shared.datetime_utils import utc_now_naive

URL = "https://api2.mercadopublico.cl/v2/compra-agil"
DESDE = utc_now_naive()
HASTA = utc_now_naive()

pytestmark = pytest.mark.asyncio


def _cliente(**kwargs) -> MercadoPublicoClient:
    return MercadoPublicoClient(api_key="ticket", espera_base=0, **kwargs)


def _pagina(prefijo: str, items: int, total_paginas: int) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "payload": {
                "items": [{"codigo": f"{prefijo}-{i}"} for i in range(items)],
                "paginacion": {"total_paginas": total_paginas},
            }
        },
    )


class TestCallbackPorPagina:
    @respx.mock
    async def test_se_llama_una_vez_por_pagina_y_en_orden(self):
        respx.get(URL).mock(side_effect=[_pagina("A", 2, 2), _pagina("B", 1, 2)])
        recibidas: list[list[str]] = []

        async def al_recibir(items):
            recibidas.append([i["codigo"] for i in items])

        listado = await _cliente().get_tenders(
            DESDE, HASTA, 100, al_recibir_pagina=al_recibir
        )

        assert recibidas == [["A-0", "A-1"], ["B-0"]]
        assert len(listado.items) == 3

    @respx.mock
    async def test_se_llama_antes_de_pedir_la_pagina_siguiente(self):
        """Si la segunda página se cae, la primera ya se entregó."""
        respx.get(URL).mock(
            side_effect=[_pagina("A", 2, 2)] + [httpx.Response(504)] * 10
        )
        recibidas: list[int] = []

        async def al_recibir(items):
            recibidas.append(len(items))

        listado = await _cliente().get_tenders(
            DESDE, HASTA, 100, al_recibir_pagina=al_recibir
        )

        assert recibidas == [2]
        assert listado.completo is False

    @respx.mock
    async def test_sin_callback_funciona_como_antes(self):
        respx.get(URL).mock(return_value=_pagina("A", 3, 1))

        listado = await _cliente().get_tenders(DESDE, HASTA, 100)

        assert len(listado.items) == 3


class TestIntentosDeDetalle:
    @respx.mock
    async def test_respeta_los_intentos_configurados(self):
        ruta = respx.get(f"{URL}/LIC-1").mock(return_value=httpx.Response(504))

        with pytest.raises(ErrorTransitorioMercadoPublico):
            await _cliente(intentos_detalle=2).get_tender_detail("LIC-1")

        assert ruta.call_count == 2

    @respx.mock
    async def test_por_defecto_son_cuatro(self):
        ruta = respx.get(f"{URL}/LIC-1").mock(return_value=httpx.Response(504))

        with pytest.raises(ErrorTransitorioMercadoPublico):
            await _cliente().get_tender_detail("LIC-1")

        assert ruta.call_count == 4

    @respx.mock
    async def test_se_puede_cambiar_entre_pasadas(self):
        ruta = respx.get(f"{URL}/LIC-1").mock(return_value=httpx.Response(504))
        cliente = _cliente(intentos_detalle=3)
        cliente.intentos_detalle = 1

        with pytest.raises(ErrorTransitorioMercadoPublico):
            await cliente.get_tender_detail("LIC-1")

        assert ruta.call_count == 1


class TestContadorDePeticiones:
    @respx.mock
    async def test_cuenta_los_reintentos(self):
        respx.get(f"{URL}/LIC-1").mock(
            side_effect=[
                httpx.Response(504),
                httpx.Response(200, json={"payload": {"codigo": "LIC-1"}}),
            ]
        )
        respx.get(URL).mock(return_value=_pagina("A", 1, 1))
        cliente = _cliente()

        await cliente.get_tender_detail("LIC-1")
        await cliente.get_tenders(DESDE, HASTA, 100)

        assert cliente.peticiones == 3


class TestPresupuesto:
    @respx.mock
    async def test_el_detalle_se_detiene_al_llegar_al_maximo(self):
        ruta = respx.get(f"{URL}/LIC-1").mock(return_value=httpx.Response(504))
        cliente = _cliente(max_peticiones=3)

        with pytest.raises(PresupuestoAgotadoError):
            await cliente.get_tender_detail("LIC-1")

        assert ruta.call_count == 3
        assert cliente.peticiones == 3

    @respx.mock
    async def test_agotar_el_presupuesto_no_rota_el_ticket(self):
        respx.get(f"{URL}/LIC-1").mock(return_value=httpx.Response(504))
        cliente = MercadoPublicoClient(
            api_keys=["uno", "dos"], espera_base=0, max_peticiones=1
        )

        with pytest.raises(PresupuestoAgotadoError):
            await cliente.get_tender_detail("LIC-1")

        assert cliente.api_key == "uno"

    @respx.mock
    async def test_el_listado_queda_incompleto_al_llegar_al_maximo(self):
        ruta = respx.get(URL).mock(
            side_effect=[_pagina("A", 2, 3), _pagina("B", 2, 3), _pagina("C", 2, 3)]
        )
        cliente = _cliente(max_peticiones=2)

        listado = await cliente.get_tenders(DESDE, HASTA, 100)

        assert ruta.call_count == 2
        assert listado.completo is False
        assert len(listado.items) == 4
