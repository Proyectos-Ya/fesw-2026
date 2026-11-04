"""Listado en paralelo y métricas por petición (plan 305).

- **Paralelo.** La página 1 va sola porque dice cuántas hay. El resto va por
  tandas de `concurrencia_listado` páginas, y cada tanda se entrega **en orden**:
  un código repetido en dos páginas no puede aplicarse con el dato viejo encima
  del nuevo. Medido el 2026-10-13: una ventana de 2 h son ~150 páginas de ~13 s;
  de a una son 32 min, cerca del tope de 50 en hora punta.
- **Métricas.** Cada petición queda anotada con su tipo, su resultado y su
  latencia, para el resumen de cada corrida en los logs.
"""

import asyncio

import httpx
import pytest
import respx

from app.infrastructure.services.tenders.mercado_publico_client import (
    ErrorTransitorioMercadoPublico,
    MercadoPublicoClient,
)
from app.shared.datetime_utils import utc_now_naive

URL = "https://api2.mercadopublico.cl/v2/compra-agil"
DESDE = utc_now_naive()
HASTA = utc_now_naive()

pytestmark = pytest.mark.asyncio


def _pagina(numero: int, total: int, items: int = 10) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "payload": {
                "items": [{"codigo": f"P{numero}-{i}"} for i in range(items)],
                "paginacion": {"total_paginas": total},
            }
        },
    )


def _por_pagina(total: int, *, caidas: set[int] = frozenset(), demoras=None):
    """Responde según `numero_pagina`, como la API, sin depender del orden."""
    en_vuelo = {"ahora": 0, "pico": 0}

    async def responder(request: httpx.Request) -> httpx.Response:
        numero = int(request.url.params["numero_pagina"])
        en_vuelo["ahora"] += 1
        en_vuelo["pico"] = max(en_vuelo["pico"], en_vuelo["ahora"])
        try:
            await asyncio.sleep((demoras or {}).get(numero, 0.01))
            if numero in caidas:
                return httpx.Response(504)
            return _pagina(numero, total)
        finally:
            en_vuelo["ahora"] -= 1

    return responder, en_vuelo


def _cliente(**kwargs) -> MercadoPublicoClient:
    return MercadoPublicoClient(api_key="t", espera_base=0, **kwargs)


class TestEnParalelo:
    @respx.mock
    async def test_trae_todas_las_paginas(self):
        responder, _ = _por_pagina(7)
        respx.get(URL).mock(side_effect=responder)

        listado = await _cliente(concurrencia_listado=3).get_tenders(DESDE, HASTA, 1000)

        assert listado.completo is True
        assert len(listado.items) == 70

    @respx.mock
    async def test_pide_varias_a_la_vez_sin_pasar_el_limite(self):
        responder, en_vuelo = _por_pagina(10)
        respx.get(URL).mock(side_effect=responder)

        await _cliente(concurrencia_listado=3).get_tenders(DESDE, HASTA, 1000)

        assert en_vuelo["pico"] == 3

    @respx.mock
    async def test_entrega_las_paginas_en_orden_aunque_lleguen_desordenadas(self):
        # La página 2 tarda más que la 3 y la 4.
        responder, _ = _por_pagina(4, demoras={2: 0.1})
        respx.get(URL).mock(side_effect=responder)
        orden: list[str] = []

        async def al_recibir(items):
            orden.append(items[0]["codigo"].split("-")[0])

        await _cliente(concurrencia_listado=3).get_tenders(
            DESDE, HASTA, 1000, al_recibir_pagina=al_recibir
        )

        assert orden == ["P1", "P2", "P3", "P4"]

    @respx.mock
    async def test_una_pagina_caida_deja_el_listado_incompleto_y_sigue(self):
        responder, _ = _por_pagina(6, caidas={3})
        respx.get(URL).mock(side_effect=responder)

        listado = await _cliente(concurrencia_listado=3).get_tenders(DESDE, HASTA, 1000)

        assert listado.completo is False
        assert len(listado.items) == 50

    @respx.mock
    async def test_tres_caidas_seguidas_cortan(self):
        responder, _ = _por_pagina(10, caidas={2, 3, 4})
        ruta = respx.get(URL).mock(side_effect=responder)

        listado = await _cliente(concurrencia_listado=3).get_tenders(DESDE, HASTA, 1000)

        assert listado.completo is False
        pedidas = {int(c.request.url.params["numero_pagina"]) for c in ruta.calls}
        assert max(pedidas) == 4

    @respx.mock
    async def test_respeta_el_tope_de_items(self):
        responder, _ = _por_pagina(10)
        respx.get(URL).mock(side_effect=responder)

        listado = await _cliente(concurrencia_listado=3).get_tenders(DESDE, HASTA, 25)

        assert len(listado.items) == 25
        assert listado.completo is False

    @respx.mock
    async def test_por_defecto_va_de_a_una(self):
        responder, en_vuelo = _por_pagina(5)
        respx.get(URL).mock(side_effect=responder)

        await _cliente().get_tenders(DESDE, HASTA, 1000)

        assert en_vuelo["pico"] == 1


class TestMetricas:
    @respx.mock
    async def test_resume_resultados_y_latencias_por_tipo(self):
        respx.get(URL).mock(side_effect=[httpx.Response(504), _pagina(1, 1)])
        respx.get(f"{URL}/LIC-1").mock(
            return_value=httpx.Response(200, json={"payload": {"codigo": "LIC-1"}})
        )
        cliente = _cliente()

        await cliente.get_tenders(DESDE, HASTA, 1000)
        await cliente.get_tender_detail("LIC-1")

        resumen = cliente.resumen()
        assert resumen["listado"]["peticiones"] == 2
        assert resumen["listado"]["por_resultado"] == {"504": 1, "200": 1}
        assert resumen["detalle"]["peticiones"] == 1
        assert resumen["detalle"]["por_resultado"] == {"200": 1}
        assert resumen["listado"]["p50_s"] >= 0
        assert "p90_s" in resumen["detalle"]

    @respx.mock
    async def test_anota_los_timeouts_por_tipo_de_error(self):
        respx.get(f"{URL}/LIC-1").mock(side_effect=httpx.ReadTimeout("lento"))
        cliente = _cliente(intentos_detalle=2)

        with pytest.raises(ErrorTransitorioMercadoPublico):
            await cliente.get_tender_detail("LIC-1")

        assert cliente.resumen()["detalle"]["por_resultado"] == {"ReadTimeout": 2}

    def test_sin_peticiones_el_resumen_queda_en_cero(self):
        resumen = _cliente().resumen()

        assert resumen["listado"]["peticiones"] == 0
        assert resumen["detalle"]["p50_s"] is None
