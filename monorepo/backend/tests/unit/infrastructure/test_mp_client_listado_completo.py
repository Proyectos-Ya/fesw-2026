"""El listado tiene que decir si alcanzó a recorrer todas las páginas.

`get_tenders` corta la paginación y devuelve lo que llevaba cuando la API falla:
un 5xx que sobrevive a los reintentos, un 429 persistente o una página ilegible.
Devolver esa lista parcial como si fuera el listado completo era inofensivo
mientras la ventana se recalculaba desde cero en cada corrida.

Deja de serlo con el cursor persistente: si la corrida se marca buena y el
cursor avanza hasta `window_to`, lo que quedó sin listar por el corte **no se
vuelve a pedir jamás**. Es exactamente el agujero que el cursor venía a tapar.
"""

import httpx
import pytest
import respx

from app.infrastructure.services.tenders.mercado_publico_client import (
    MercadoPublicoClient,
)
from app.shared.datetime_utils import utc_now_naive

URL = "https://api2.mercadopublico.cl/v2/compra-agil"
DESDE = utc_now_naive()
HASTA = utc_now_naive()

pytestmark = pytest.mark.asyncio


def _cliente() -> MercadoPublicoClient:
    return MercadoPublicoClient(api_key="ticket-de-prueba", espera_base=0)


def _pagina(items: int, total_paginas: int) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "payload": {
                "items": [{"codigo": f"C-{i}"} for i in range(items)],
                "paginacion": {"total_paginas": total_paginas},
            }
        },
    )


class TestListadoCompleto:
    @respx.mock
    async def test_recorrer_todas_las_paginas_se_reporta_completo(self):
        respx.get(URL).mock(side_effect=[_pagina(20, 2), _pagina(5, 2)])

        listado = await _cliente().get_tenders(DESDE, HASTA, 100)

        assert listado.completo is True
        assert len(listado.items) == 25

    @respx.mock
    async def test_una_sola_pagina_tambien_es_completo(self):
        respx.get(URL).mock(return_value=_pagina(3, 1))

        listado = await _cliente().get_tenders(DESDE, HASTA, 100)

        assert listado.completo is True

    @respx.mock
    async def test_quedarse_sin_items_antes_de_tiempo_es_completo(self):
        """La API dice que hay más páginas pero devuelve una vacía: no hay más."""
        respx.get(URL).mock(side_effect=[_pagina(20, 5), _pagina(0, 5)])

        listado = await _cliente().get_tenders(DESDE, HASTA, 100)

        assert listado.completo is True


class TestListadoTruncado:
    @respx.mock
    async def test_un_5xx_persistente_marca_el_listado_incompleto(self):
        respx.get(URL).mock(
            side_effect=[
                _pagina(20, 5),
                *[httpx.Response(500, json={}) for _ in range(4)],
            ]
        )

        listado = await _cliente().get_tenders(DESDE, HASTA, 100)

        assert listado.completo is False
        assert len(listado.items) == 20

    @respx.mock
    async def test_un_429_persistente_marca_el_listado_incompleto(self):
        respx.get(URL).mock(
            side_effect=[
                _pagina(20, 5),
                *[httpx.Response(429, json={}) for _ in range(4)],
            ]
        )

        listado = await _cliente().get_tenders(DESDE, HASTA, 100)

        assert listado.completo is False

    @respx.mock
    async def test_alcanzar_el_tope_pedido_no_es_un_listado_completo(self):
        """Quedan páginas sin mirar: el corte lo puso el llamador, no la API."""
        respx.get(URL).mock(return_value=_pagina(20, 99))

        listado = await _cliente().get_tenders(DESDE, HASTA, 20)

        assert listado.completo is False
        assert len(listado.items) == 20
