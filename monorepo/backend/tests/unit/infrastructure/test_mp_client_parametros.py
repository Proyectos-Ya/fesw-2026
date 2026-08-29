"""Parámetros de consulta para la carga inicial.

La sincronización diaria pregunta por lo que **cambió** en 24 h
(`ttl_cambio_ms`). Una carga inicial quiere otra cosa: lo que se **publicó** en
los últimos N días, que es un corpus y no un delta. La guía de la API los pone
en grupos distintos —`ttl_cambio_ms` y `cambio_desde/hasta` son excluyentes
entre sí, pero `publicado_desde/hasta` es otro grupo—, así que conviven.

Se suma `estado` para filtrar en el servidor: medido, `estado=publicada` sin
ventana de tiempo devuelve 504, así que siempre va acompañado.
"""

import json
from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.infrastructure.services.tenders.mercado_publico_client import (
    MercadoPublicoClient,
)

URL = "https://api2.mercadopublico.cl/v2/compra-agil"
DESDE = datetime(2026, 8, 1, tzinfo=UTC)
HASTA = datetime(2026, 8, 31, tzinfo=UTC)


def _respuesta_vacia() -> httpx.Response:
    return httpx.Response(200, json={"payload": {"items": []}})


async def _pedir(**extra) -> dict:
    ruta = respx.get(URL).mock(return_value=_respuesta_vacia())
    cliente = MercadoPublicoClient(api_key="t", espera_base=0)
    await cliente.get_tenders(DESDE, HASTA, 20, **extra)
    return dict(httpx.URL(str(ruta.calls.last.request.url)).params)


class TestComportamientoActual:
    @respx.mock
    @pytest.mark.asyncio
    async def test_sin_parametros_nuevos_sigue_usando_la_ventana_de_cambios(self):
        """La sincronización diaria no debe cambiar de comportamiento."""
        params = await _pedir()

        assert params["ttl_cambio_ms"] == str(30 * 24 * 3600 * 1000)
        assert "publicado_desde" not in params
        assert "estado" not in params


class TestVentanaDePublicacion:
    @respx.mock
    @pytest.mark.asyncio
    async def test_por_publicacion_manda_el_rango_en_iso_8601(self):
        params = await _pedir(por_publicacion=True)

        assert params["publicado_desde"] == "2026-08-01T00:00:00Z"
        assert params["publicado_hasta"] == "2026-08-31T00:00:00Z"

    @respx.mock
    @pytest.mark.asyncio
    async def test_por_publicacion_excluye_la_ventana_de_cambios(self):
        """La guía advierte que los grupos de ventana no se combinan."""
        params = await _pedir(por_publicacion=True)

        assert "ttl_cambio_ms" not in params


class TestFiltroDeEstado:
    @respx.mock
    @pytest.mark.asyncio
    async def test_el_estado_viaja_al_servidor(self):
        """Así las cerradas y desiertas ni siquiera se descargan."""
        params = await _pedir(estado="publicada")

        assert params["estado"] == "publicada"

    @respx.mock
    @pytest.mark.asyncio
    async def test_admite_varios_estados_separados_por_coma(self):
        params = await _pedir(estado="publicada,proveedor_seleccionado")

        assert params["estado"] == "publicada,proveedor_seleccionado"
