"""GET /tenders/map: marcadores del mapa de licitaciones (HU-22, #314)."""

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import OperationalError

from app.application.schemas.tender_map_schema import TenderMapResponse
from app.bootstrap.matching import get_tenders_map_use_case
from app.domain.entities.tender_map import GeoPrecision, TenderMapPoint
from app.domain.errors.tender_errors import InvalidSearchCriteria
from app.main import app
from tests.support.api_auth import autenticar


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def _caso(**kwargs) -> AsyncMock:
    caso = AsyncMock(**kwargs)
    app.dependency_overrides[get_tenders_map_use_case] = lambda: caso
    return caso


async def test_devuelve_los_marcadores_de_la_region(api: AsyncClient) -> None:
    punto = TenderMapPoint(
        id=uuid4(),
        name="Insumos",
        buyer_name="Municipalidad de Ancud",
        delivery_address="Yerbas Buenas #915",
        closing_at=datetime(2026, 11, 3, 18, 0),
        lat=-41.87,
        lng=-73.82,
        precision=GeoPrecision.COMUNA,
    )
    caso = _caso()
    caso.execute.return_value = TenderMapResponse(
        region="Los Lagos", items=[punto], total=1
    )
    await autenticar(api, email="mapa@example.com", full_name="Mapa")

    respuesta = await api.get("/tenders/map", params={"region": "Los Lagos"})

    assert respuesta.status_code == 200
    caso.execute.assert_awaited_once_with("Los Lagos")
    cuerpo = respuesta.json()
    assert cuerpo["region"] == "Los Lagos"
    assert cuerpo["total"] == 1
    assert cuerpo["is_truncated"] is False
    [item] = cuerpo["items"]
    assert item["id"] == str(punto.id)
    assert item["lat"] == -41.87 and item["lng"] == -73.82
    assert item["precision"] == "comuna"
    assert item["delivery_address"] == "Yerbas Buenas #915"
    assert item["buyer_name"] == "Municipalidad de Ancud"
    # UTC explícito, como el resto de las fechas de la API.
    assert item["closing_at"].endswith("Z") or item["closing_at"].endswith("+00:00")


async def test_una_region_desconocida_responde_422(api: AsyncClient) -> None:
    _caso().execute.side_effect = InvalidSearchCriteria("Región desconocida: 'X'.")
    await autenticar(api, email="mapa422@example.com", full_name="Mapa")

    respuesta = await api.get("/tenders/map", params={"region": "Narnia"})

    assert respuesta.status_code == 422


async def test_sin_region_responde_422(api: AsyncClient) -> None:
    _caso()
    await autenticar(api, email="mapa-sin@example.com", full_name="Mapa")

    respuesta = await api.get("/tenders/map")

    assert respuesta.status_code == 422


async def test_con_la_base_caida_responde_503(api: AsyncClient) -> None:
    _caso().execute.side_effect = OperationalError("SELECT", {}, Exception("caída"))
    await autenticar(api, email="mapa503@example.com", full_name="Mapa")

    respuesta = await api.get("/tenders/map", params={"region": "Los Lagos"})

    # El frontend lo muestra como "No se pudo cargar el mapa" con reintento.
    assert respuesta.status_code == 503


async def test_sin_sesion_responde_401(api: AsyncClient) -> None:
    respuesta = await api.get("/tenders/map", params={"region": "Los Lagos"})

    assert respuesta.status_code == 401


async def test_map_no_lo_captura_la_ruta_del_detalle(api: AsyncClient) -> None:
    """`/{tender_id}` declarada antes interpretaría "map" como UUID (422)."""
    caso = _caso()
    caso.execute.return_value = TenderMapResponse(region="Ñuble", items=[], total=0)
    await autenticar(api, email="mapa-ruta@example.com", full_name="Mapa")

    respuesta = await api.get("/tenders/map", params={"region": "Ñuble"})

    assert respuesta.status_code == 200
    assert respuesta.json()["items"] == []
