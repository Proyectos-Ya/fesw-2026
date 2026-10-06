"""El listado aguanta los 504 de hora punta en vez de rendirse a la primera página.

Medido el 2026-10-05 en el cron de estados: entre las 10:00 y las 18:00 (Chile)
el listado devolvía 504/500 casi cada hora. Con tres reintentos de 2, 4 y 8 s,
una sola página caída cortaba la paginación entera —"Página 2 no respondió…
Se detiene con 20 licitaciones listadas"— aunque las siguientes respondieran.

Dos cambios, y lo que cada test fija:

- **Más paciencia con el servidor.** Un 5xx o un timeout se reintentan más veces
  y con esperas más largas (con tope y algo de azar, para no golpear al gateway
  todos a la vez). El 429 **no** cambia: sus cuatro intentos por ticket deciden
  cuándo rotar, y eso lo fija `test_mp_client_rotacion_tickets`.
- **Saltar la página caída y seguir.** El listado igual queda marcado
  incompleto —el cursor de `sync_diaria` no avanza y la ventana se vuelve a
  pedir—, pero lo que respondió se aprovecha. Se rinde si caen varias páginas
  seguidas (la API está caída, no inestable) o si cae la primera (sin ella no se
  sabe cuántas páginas hay).
"""

import httpx
import pytest
import respx

from app.infrastructure.services.tenders.mercado_publico_client import (
    ESPERA_MAXIMA_REINTENTO,
    INTENTOS_SERVIDOR_LISTADO,
    PAGINAS_CAIDAS_SEGUIDAS_MAX,
    MercadoPublicoClient,
    espera_reintento,
)
from app.shared.datetime_utils import utc_now_naive

URL = "https://api2.mercadopublico.cl/v2/compra-agil"
DESDE = utc_now_naive()
HASTA = utc_now_naive()

pytestmark = pytest.mark.asyncio


def _cliente() -> MercadoPublicoClient:
    return MercadoPublicoClient(api_key="ticket-de-prueba", espera_base=0)


def _pagina(numero: int, total_paginas: int, items: int = 20) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "payload": {
                "items": [{"codigo": f"P{numero}-{i}"} for i in range(items)],
                "paginacion": {"total_paginas": total_paginas},
            }
        },
    )


def _api(total_paginas: int, caidas: set[int]):
    """Una API que responde todas las páginas salvo las `caidas`, que dan 504."""

    def responder(request: httpx.Request) -> httpx.Response:
        numero = int(request.url.params["numero_pagina"])
        if numero in caidas:
            return httpx.Response(504)
        return _pagina(numero, total_paginas)

    return responder


def _paginas_pedidas(ruta) -> list[int]:
    return [int(c.request.url.params["numero_pagina"]) for c in ruta.calls]


class TestMasPacienciaConElServidor:
    @respx.mock
    async def test_un_504_que_dura_mas_que_antes_se_recupera(self):
        """Cuatro 504 seguidos agotaban los intentos; ahora se sigue esperando."""
        ruta = respx.get(URL).mock(
            side_effect=[*[httpx.Response(504)] * 4, _pagina(1, 1)]
        )

        listado = await _cliente().get_tenders(DESDE, HASTA, 100)

        assert listado.completo is True
        assert len(listado.items) == 20
        assert ruta.call_count == 5

    @respx.mock
    async def test_los_intentos_ante_5xx_tienen_un_limite(self):
        ruta = respx.get(URL).mock(return_value=httpx.Response(504))

        listado = await _cliente().get_tenders(DESDE, HASTA, 100)

        assert listado.completo is False
        assert ruta.call_count == INTENTOS_SERVIDOR_LISTADO

    @respx.mock
    async def test_un_429_persistente_no_gana_intentos_de_mas(self):
        """El 429 decide la rotación de tickets: sigue con sus cuatro intentos."""
        ruta = respx.get(URL).mock(return_value=httpx.Response(429, json={}))

        await _cliente().get_tenders(DESDE, HASTA, 100)

        assert ruta.call_count == 4


class TestEsperaEntreReintentos:
    def test_crece_con_cada_intento(self):
        sin_azar = [espera_reintento(1.0, i, azar=lambda: 1.0) for i in (1, 2, 3)]

        assert sin_azar == [2.0, 4.0, 8.0]

    def test_no_pasa_del_tope(self):
        assert espera_reintento(1.0, 20, azar=lambda: 1.0) == ESPERA_MAXIMA_REINTENTO

    def test_el_azar_solo_acorta_hasta_la_mitad(self):
        """Repartir los reintentos sin perder del todo la espera."""
        assert espera_reintento(1.0, 3, azar=lambda: 0.0) == 4.0

    def test_con_base_cero_no_duerme(self):
        assert espera_reintento(0.0, 5) == 0.0


class TestSaltarLaPaginaCaida:
    @respx.mock
    async def test_una_pagina_caida_al_medio_no_corta_las_siguientes(self):
        ruta = respx.get(URL).mock(side_effect=_api(total_paginas=4, caidas={2}))

        listado = await _cliente().get_tenders(DESDE, HASTA, 1000)

        codigos = {item["codigo"] for item in listado.items}
        assert {"P1-0", "P3-0", "P4-0"} <= codigos
        assert not any(c.startswith("P2-") for c in codigos)
        assert 4 in _paginas_pedidas(ruta)

    @respx.mock
    async def test_saltar_una_pagina_deja_el_listado_incompleto(self):
        """Faltan 20: el cursor no puede avanzar como si estuviera todo."""
        respx.get(URL).mock(side_effect=_api(total_paginas=3, caidas={2}))

        listado = await _cliente().get_tenders(DESDE, HASTA, 1000)

        assert listado.completo is False

    @respx.mock
    async def test_si_cae_la_primera_no_sigue(self):
        """Sin la primera no se sabe cuántas páginas hay."""
        ruta = respx.get(URL).mock(side_effect=_api(total_paginas=5, caidas={1}))

        listado = await _cliente().get_tenders(DESDE, HASTA, 1000)

        assert listado.items == []
        assert listado.completo is False
        assert set(_paginas_pedidas(ruta)) == {1}

    @respx.mock
    async def test_varias_caidas_seguidas_detienen_la_paginacion(self):
        """Ya no es una página inestable: la API está caída."""
        caidas = set(range(2, 2 + PAGINAS_CAIDAS_SEGUIDAS_MAX + 5))
        ruta = respx.get(URL).mock(side_effect=_api(total_paginas=50, caidas=caidas))

        listado = await _cliente().get_tenders(DESDE, HASTA, 1000)

        assert listado.completo is False
        assert max(_paginas_pedidas(ruta)) == 1 + PAGINAS_CAIDAS_SEGUIDAS_MAX

    @respx.mock
    async def test_una_pagina_buena_reinicia_la_cuenta_de_caidas(self):
        caidas = {2, 3, 5, 6}  # nunca más de dos seguidas
        ruta = respx.get(URL).mock(side_effect=_api(total_paginas=7, caidas=caidas))

        await _cliente().get_tenders(DESDE, HASTA, 1000)

        assert 7 in _paginas_pedidas(ruta)

    @respx.mock
    async def test_un_429_persistente_sigue_cortando(self):
        """Cuota agotada en todos los tickets: seguir pidiendo solo gasta más."""

        def responder(request: httpx.Request) -> httpx.Response:
            if request.url.params["numero_pagina"] == "1":
                return _pagina(1, 5)
            return httpx.Response(429, json={})

        ruta = respx.get(URL).mock(side_effect=responder)

        listado = await _cliente().get_tenders(DESDE, HASTA, 1000)

        assert listado.completo is False
        assert set(_paginas_pedidas(ruta)) == {1, 2}
