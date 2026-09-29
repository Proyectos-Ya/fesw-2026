"""La API compara las horas en hora de Chile como si fueran UTC.

Medido contra la API real el 2026-09-29 a las 12:48 de Chile (15:48 UTC, Chile
en UTC-3):

- `ttl_cambio_ms` de 3,0 h devolvió **0** cambios; de 3,1 h, 99 (los últimos
  ~6 minutos); de 4 h, 1.637. La ventana efectiva es `ttl` menos el desfase de
  Chile: la API resta el ttl a su "ahora" en UTC y lo compara contra fechas
  guardadas en hora de Chile.
- `publicado_desde/hasta` con la última hora real en UTC devolvió **0**; la
  misma ventana corrida 3 h hacia atrás, 498. Los bordes se leen como hora de
  Chile aunque lleven Z.

Es la otra cara de lo que se vio en el listado (las fechas con Z son hora de
Chile): la API guarda y compara hora de pared de Chile con una etiqueta UTC.
"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from app.infrastructure.services.tenders.mercado_publico_client import (
    MercadoPublicoClient,
)

URL = "https://api2.mercadopublico.cl/v2/compra-agil"
# Septiembre: Chile en horario de verano, UTC-3.
HASTA_SEPT = datetime(2026, 9, 29, 15, 48)
# Julio: Chile en horario de invierno, UTC-4.
HASTA_JULIO = datetime(2026, 7, 15, 15, 0)


async def _params(desde: datetime, hasta: datetime, **extra) -> dict:
    ruta = respx.get(URL).mock(
        return_value=httpx.Response(200, json={"payload": {"items": []}})
    )
    cliente = MercadoPublicoClient(api_key="t", espera_base=0)
    await cliente.get_tenders(desde, hasta, 20, **extra)
    return dict(httpx.URL(str(ruta.calls.last.request.url)).params)


class TestVentanaDeCambios:
    @respx.mock
    @pytest.mark.asyncio
    async def test_suma_el_desfase_de_chile_en_verano(self):
        """Pedir 6 h reales exige mandar 9 h cuando Chile está en UTC-3."""
        params = await _params(HASTA_SEPT - timedelta(hours=6), HASTA_SEPT)

        assert params["ttl_cambio_ms"] == str(9 * 3600 * 1000)

    @respx.mock
    @pytest.mark.asyncio
    async def test_suma_el_desfase_de_chile_en_invierno(self):
        params = await _params(HASTA_JULIO - timedelta(hours=6), HASTA_JULIO)

        assert params["ttl_cambio_ms"] == str(10 * 3600 * 1000)

    @respx.mock
    @pytest.mark.asyncio
    async def test_acepta_fechas_con_zona(self):
        hasta = HASTA_SEPT.replace(tzinfo=UTC)
        params = await _params(hasta - timedelta(hours=6), hasta)

        assert params["ttl_cambio_ms"] == str(9 * 3600 * 1000)
