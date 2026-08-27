"""Pruebas de extremo a extremo de GET /tenders/search (HdU 07)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import AsyncClient, Headers
from qdrant_client.http.exceptions import UnexpectedResponse
from sqlalchemy.exc import OperationalError

from app.application.schemas.tender_schema import TenderSearchResult
from app.bootstrap import get_search_tenders_use_case
from app.domain.entities.tender import Tender
from app.domain.errors.tender_errors import InvalidSearchCriteria
from app.main import app
from app.shared.regions import CHILE_REGIONS


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


async def _login(api: AsyncClient) -> None:
    datos = {
        "email": "buscadora@example.com",
        "password": "supersecretpassword",
        "full_name": "Ana Buscadora",
    }
    await api.post("/auth/register", json=datos)
    await api.post(
        "/auth/login", json={"email": datos["email"], "password": datos["password"]}
    )


def _tender(nombre: str = "Construcción de techumbre") -> Tender:
    now = datetime.now(UTC).replace(tzinfo=None)
    return Tender(
        id=uuid4(),
        code=f"COT-{uuid4()}",
        name=nombre,
        description="Reparación de cubierta metálica",
        status_id=1,
        status_code="publicada",
        published_at=now - timedelta(days=1),
        closing_at=now + timedelta(days=5),
        last_change_at=now,
        buyer_rut="12.345.678-9",
        buyer_unit="Obras",
        items=[],
    )


def _mock_use_case(resultado: TenderSearchResult | None = None) -> AsyncMock:
    mock = AsyncMock()
    mock.execute.return_value = resultado or TenderSearchResult(
        items=[], total=0, is_truncated=False
    )
    app.dependency_overrides[get_search_tenders_use_case] = lambda: mock
    return mock


# ---------------------------------------------------------------------------
# Camino feliz
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_devuelve_resultados_con_total(api: AsyncClient) -> None:
    tender = _tender()
    _mock_use_case(TenderSearchResult(items=[tender], total=137, is_truncated=True))
    await _login(api)

    response = await api.get("/tenders/search?q=techumbre")

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Construcción de techumbre"
    assert data["total"] == 137
    assert data["is_truncated"] is True


@pytest.mark.asyncio
async def test_sin_coincidencias_responde_200_y_no_404(api: AsyncClient) -> None:
    """Cero resultados es una respuesta válida.

    El criterio pide comunicar que no hay resultados y sugerir flexibilizar los
    filtros; un 404 haría que el frontend lo tratara como error.
    """
    _mock_use_case()
    await _login(api)

    response = await api.get("/tenders/search?q=algo+inexistente")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "is_truncated": False}


@pytest.mark.asyncio
async def test_la_busqueda_sin_texto_es_valida(api: AsyncClient) -> None:
    """Solo filtros, sin `q`: ordena por afinidad con la empresa."""
    mock = _mock_use_case()
    await _login(api)

    response = await api.get("/tenders/search?status_codes=publicada")

    assert response.status_code == 200
    assert mock.execute.call_args.kwargs["q"] is None


# ---------------------------------------------------------------------------
# Traducción de parámetros
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_traduce_los_nombres_de_region_a_ids(api: AsyncClient) -> None:
    """El frontend filtra por nombre; el criterio viaja con ids."""
    mock = _mock_use_case()
    await _login(api)

    response = await api.get(
        f"/tenders/search?regions={CHILE_REGIONS[13]}&regions={CHILE_REGIONS[5]}"
    )

    assert response.status_code == 200
    criteria = mock.execute.call_args.kwargs["criteria"]
    assert criteria.region_ids == [13, 5]


@pytest.mark.asyncio
async def test_los_filtros_llegan_al_caso_de_uso(api: AsyncClient) -> None:
    mock = _mock_use_case()
    await _login(api)

    response = await api.get(
        "/tenders/search"
        "?q=cables"
        "&status_codes=publicada"
        "&min_amount=100000"
        "&max_amount=500000"
        "&closing_from=2026-09-01T00:00:00"
        "&offset=500"
    )

    assert response.status_code == 200
    kwargs = mock.execute.call_args.kwargs
    criteria = kwargs["criteria"]
    assert kwargs["q"] == "cables"
    assert kwargs["offset"] == 500
    assert criteria.status_codes == ["publicada"]
    assert criteria.min_amount == 100_000
    assert criteria.max_amount == 500_000
    assert criteria.closing_from == datetime(2026, 9, 1, 0, 0, 0)


# ---------------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sin_sesion_responde_401(api: AsyncClient) -> None:
    _mock_use_case()

    response = await api.get("/tenders/search?q=cables")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_criterios_incoherentes_responden_422(api: AsyncClient) -> None:
    mock = _mock_use_case()
    mock.execute.side_effect = InvalidSearchCriteria(
        "El rango de cierre está invertido."
    )
    await _login(api)

    response = await api.get(
        "/tenders/search?closing_from=2026-09-10T00:00:00&closing_to=2026-09-01T00:00:00"
    )

    assert response.status_code == 422
    assert "invertido" in response.json()["detail"]


@pytest.mark.asyncio
async def test_una_region_desconocida_responde_422(api: AsyncClient) -> None:
    """Ignorarla ensancharía la búsqueda en silencio.

    El usuario vería resultados de regiones que no pidió sin ninguna señal.
    """
    _mock_use_case()
    await _login(api)

    response = await api.get("/tenders/search?regions=Región+Inventada")

    assert response.status_code == 422
    assert "desconocida" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_un_monto_negativo_lo_rechaza_la_validacion_de_query(
    api: AsyncClient,
) -> None:
    _mock_use_case()
    await _login(api)

    response = await api.get("/tenders/search?min_amount=-5")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_un_texto_demasiado_largo_se_rechaza(api: AsyncClient) -> None:
    _mock_use_case()
    await _login(api)

    response = await api.get(f"/tenders/search?q={'a' * 201}")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_qdrant_caido_responde_503(api: AsyncClient) -> None:
    """El criterio pide avisar sin bloquear el resto de la plataforma."""
    mock = _mock_use_case()
    mock.execute.side_effect = UnexpectedResponse(
        status_code=500, reason_phrase="", content=b"", headers=Headers()
    )
    await _login(api)

    response = await api.get("/tenders/search?q=cables")

    assert response.status_code == 503
    assert "no se pudo completar" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_postgres_caido_responde_503(api: AsyncClient) -> None:
    mock = _mock_use_case()
    mock.execute.side_effect = OperationalError("SELECT 1", {}, Exception("caída"))
    await _login(api)

    response = await api.get("/tenders/search")

    assert response.status_code == 503


# ---------------------------------------------------------------------------
# limit: permite paginar contra el backend (issue #123)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_limit_por_defecto_es_100(api: AsyncClient) -> None:
    mock = _mock_use_case()
    await _login(api)

    response = await api.get("/tenders/search?q=cables")

    assert response.status_code == 200
    assert mock.execute.call_args.kwargs["limit"] == 100


@pytest.mark.asyncio
async def test_permite_paginar_contra_el_backend(api: AsyncClient) -> None:
    """`limit=20&offset=40` es la página 3 servida por el servidor."""
    mock = _mock_use_case()
    await _login(api)

    response = await api.get("/tenders/search?q=cables&limit=20&offset=40")

    assert response.status_code == 200
    kwargs = mock.execute.call_args.kwargs
    assert kwargs["limit"] == 20
    assert kwargs["offset"] == 40


@pytest.mark.asyncio
async def test_un_limit_sobre_el_maximo_se_rechaza(api: AsyncClient) -> None:
    _mock_use_case()
    await _login(api)

    response = await api.get("/tenders/search?limit=501")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_un_limit_de_cero_se_rechaza(api: AsyncClient) -> None:
    _mock_use_case()
    await _login(api)

    response = await api.get("/tenders/search?limit=0")

    assert response.status_code == 422
