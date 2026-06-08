from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.domain.entities.licitacion import ItemLicitacion, Licitacion
from app.infrastructure.services.mercado_publico_client import MercadoPublicoClient

API_KEY = "test-ticket-123"


def _make_raw_item(
    codigo: str = "0001-1-LQ24",
    nombre: str = "Adquisicion de equipos",
    fecha_cierre: str = "15-08-2026 10:30:00",
    estado_codigo: str = "AC",
    organismo: str = "Municipalidad Test",
    region: str = "Metropolitana de Santiago",
    monto: float | None = 5_000_000.0,
    descripcion: str | None = None,
    items: list | None = None,
) -> dict:
    return {
        "CodigoExterno": codigo,
        "Nombre": nombre,
        "FechaCierre": fecha_cierre,
        "EstadoCodigo": estado_codigo,
        "Descripcion": descripcion,
        "MontoEstimado": monto,
        "Comprador": {
            "NombreOrganismo": organismo,
            "RegionUnidad": region,
        },
        "Items": {"Listado": items or []},
    }


def _mock_response(listado: list) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.json.return_value = {"Listado": listado}
    resp.raise_for_status = MagicMock()
    return resp


@pytest.fixture
def http_client() -> AsyncMock:
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def client(http_client: AsyncMock) -> MercadoPublicoClient:
    return MercadoPublicoClient(api_key=API_KEY, http_client=http_client)


# ---------------------------------------------------------------------------
# fetch_licitaciones — happy path
# ---------------------------------------------------------------------------


async def test_fetch_retorna_lista_de_licitaciones(
    client: MercadoPublicoClient, http_client: AsyncMock
) -> None:
    http_client.get.return_value = _mock_response(
        [_make_raw_item("0001-1-LQ24"), _make_raw_item("0002-1-LQ24")]
    )

    resultado = await client.fetch_licitaciones("activas", limit=2, offset=0)

    assert len(resultado) == 2
    assert all(isinstance(r, Licitacion) for r in resultado)
    assert resultado[0].codigo_externo == "0001-1-LQ24"
    assert resultado[1].codigo_externo == "0002-1-LQ24"


async def test_fetch_listado_vacio_retorna_lista_vacia(
    client: MercadoPublicoClient, http_client: AsyncMock
) -> None:
    http_client.get.return_value = _mock_response([])

    resultado = await client.fetch_licitaciones("activas", limit=10, offset=0)

    assert resultado == []


async def test_fetch_sin_clave_listado_retorna_lista_vacia(
    client: MercadoPublicoClient, http_client: AsyncMock
) -> None:
    resp = MagicMock(spec=httpx.Response)
    resp.json.return_value = {}
    resp.raise_for_status = MagicMock()
    http_client.get.return_value = resp

    resultado = await client.fetch_licitaciones("activas", limit=10, offset=0)

    assert resultado == []


# ---------------------------------------------------------------------------
# Parámetros de la petición HTTP
# ---------------------------------------------------------------------------


async def test_fetch_envia_api_key_como_ticket(
    client: MercadoPublicoClient, http_client: AsyncMock
) -> None:
    http_client.get.return_value = _mock_response([])

    await client.fetch_licitaciones("activas", limit=10, offset=0)

    params = http_client.get.call_args.kwargs["params"]
    assert params["ticket"] == API_KEY


async def test_fetch_envia_estado_y_cantidad(
    client: MercadoPublicoClient, http_client: AsyncMock
) -> None:
    http_client.get.return_value = _mock_response([])

    await client.fetch_licitaciones("cerradas", limit=25, offset=0)

    params = http_client.get.call_args.kwargs["params"]
    assert params["estado"] == "cerradas"
    assert params["cantidad"] == 25


async def test_fetch_convierte_offset_a_pagina(
    client: MercadoPublicoClient, http_client: AsyncMock
) -> None:
    http_client.get.return_value = _mock_response([])

    await client.fetch_licitaciones("activas", limit=10, offset=20)

    params = http_client.get.call_args.kwargs["params"]
    assert params["pagina"] == 3  # offset=20, limit=10 → página 3


async def test_fetch_offset_cero_es_pagina_uno(
    client: MercadoPublicoClient, http_client: AsyncMock
) -> None:
    http_client.get.return_value = _mock_response([])

    await client.fetch_licitaciones("activas", limit=10, offset=0)

    params = http_client.get.call_args.kwargs["params"]
    assert params["pagina"] == 1


async def test_fetch_llama_raise_for_status(
    client: MercadoPublicoClient, http_client: AsyncMock
) -> None:
    mock_resp = _mock_response([])
    http_client.get.return_value = mock_resp

    await client.fetch_licitaciones("activas", limit=10, offset=0)

    mock_resp.raise_for_status.assert_called_once()


# ---------------------------------------------------------------------------
# Mapeo de campos
# ---------------------------------------------------------------------------


async def test_mapeo_campos_basicos(
    client: MercadoPublicoClient, http_client: AsyncMock
) -> None:
    http_client.get.return_value = _mock_response(
        [
            _make_raw_item(
                codigo="9999-1-LQ26",
                nombre="Servicio de limpieza",
                organismo="Gobernación Test",
                region="Valparaíso",
                monto=3_000_000.0,
            )
        ]
    )

    result = (await client.fetch_licitaciones("activas", limit=1, offset=0))[0]

    assert result.codigo_externo == "9999-1-LQ26"
    assert result.nombre == "Servicio de limpieza"
    assert result.organismo_nombre == "Gobernación Test"
    assert result.region == "Valparaíso"
    assert result.monto_estimado == 3_000_000.0


async def test_mapeo_items(
    client: MercadoPublicoClient, http_client: AsyncMock
) -> None:
    raw_items = [
        {"NombreProducto": "Escobas", "Descripcion": "Industriales"},
        {"NombreProducto": "Detergente"},
    ]
    http_client.get.return_value = _mock_response(
        [_make_raw_item(items=raw_items)]
    )

    result = (await client.fetch_licitaciones("activas", limit=1, offset=0))[0]

    assert len(result.items) == 2
    assert isinstance(result.items[0], ItemLicitacion)
    assert result.items[0].nombre == "Escobas"
    assert result.items[0].descripcion == "Industriales"
    assert result.items[1].nombre == "Detergente"
    assert result.items[1].descripcion is None


# ---------------------------------------------------------------------------
# Parseo de fecha
# ---------------------------------------------------------------------------


def test_parse_fecha_retorna_datetime_utc() -> None:
    result = MercadoPublicoClient._parse_fecha("15-08-2026 10:30:00")

    assert result == datetime(2026, 8, 15, 10, 30, 0, tzinfo=UTC)


def test_parse_fecha_asigna_timezone_utc() -> None:
    result = MercadoPublicoClient._parse_fecha("01-01-2026 00:00:00")

    assert result.tzinfo is UTC
