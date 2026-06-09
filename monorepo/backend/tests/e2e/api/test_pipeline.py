from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.domain.entities.matching_result import MatchingResult as ResultadoMatching
from app.domain.models.tender_schema import IngestResult
from app.domain.models.matching_schema import MatchResult
from app.main import app
from app.routers.licitaciones import get_ingest_use_case
from app.routers.matching import get_match_use_case, get_obtener_score_use_case


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /licitaciones/ingest
# ---------------------------------------------------------------------------


async def test_ingest_retorna_resultado(client: AsyncClient) -> None:
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = IngestResult(
        procesadas=5, duplicadas=2, errores=0, version_modelo="bge-m3-v1"
    )
    app.dependency_overrides[get_ingest_use_case] = lambda: mock_uc

    response = await client.post("/licitaciones/ingest", json={})

    assert response.status_code == 200
    data = response.json()
    assert data["procesadas"] == 5
    assert data["duplicadas"] == 2
    assert data["errores"] == 0
    assert data["version_modelo"] == "bge-m3-v1"


async def test_ingest_acepta_parametros_opcionales(client: AsyncClient) -> None:
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = IngestResult(
        procesadas=10, duplicadas=0, errores=0, version_modelo="bge-m3-v1"
    )
    app.dependency_overrides[get_ingest_use_case] = lambda: mock_uc

    response = await client.post(
        "/licitaciones/ingest",
        json={"estado": "cerradas", "limit": 50, "offset": 100},
    )

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /matching
# ---------------------------------------------------------------------------


async def test_match_retorna_resultado(client: AsyncClient) -> None:
    proveedor_id = uuid4()
    licitacion_id = uuid4()

    resultado = ResultadoMatching(
        supplier_id=proveedor_id,
        tender_id=licitacion_id,
        similarity_score=0.92,
        final_score=0.92,
        model_version="bge-m3-v1",
    )
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = MatchResult(
        resultados=[resultado], version_modelo="bge-m3-v1"
    )
    app.dependency_overrides[get_match_use_case] = lambda: mock_uc

    response = await client.post(
        "/matching/", json={"proveedor_id": str(proveedor_id)}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["version_modelo"] == "bge-m3-v1"
    assert len(data["resultados"]) == 1
    assert data["resultados"][0]["similarity_score"] == 0.92


async def test_match_proveedor_no_encontrado_retorna_404(
    client: AsyncClient,
) -> None:
    from app.domain.errors.supplier_errors import SupplierNotFound

    mock_uc = AsyncMock()
    mock_uc.execute.side_effect = SupplierNotFound("rut-inexistente")
    app.dependency_overrides[get_match_use_case] = lambda: mock_uc

    response = await client.post(
        "/matching/", json={"proveedor_id": str(uuid4())}
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /matching/{proveedor_id}/{licitacion_id}
# ---------------------------------------------------------------------------


async def test_obtener_score_retorna_resultado_matching(
    client: AsyncClient,
) -> None:
    proveedor_id = uuid4()
    licitacion_id = uuid4()

    resultado = ResultadoMatching(
        supplier_id=proveedor_id,
        tender_id=licitacion_id,
        similarity_score=0.88,
        final_score=0.88,
        model_version="bge-m3-v1",
    )
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = resultado
    app.dependency_overrides[get_obtener_score_use_case] = lambda: mock_uc

    response = await client.get(f"/matching/{proveedor_id}/{licitacion_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["similarity_score"] == 0.88
    assert data["model_version"] == "bge-m3-v1"


async def test_obtener_score_no_encontrado_retorna_404(
    client: AsyncClient,
) -> None:
    from app.domain.errors.matching_errors import ScoreMatchingNoEncontrado

    mock_uc = AsyncMock()
    mock_uc.execute.side_effect = ScoreMatchingNoEncontrado(
        str(uuid4()), str(uuid4())
    )
    app.dependency_overrides[get_obtener_score_use_case] = lambda: mock_uc

    response = await client.get(f"/matching/{uuid4()}/{uuid4()}")

    assert response.status_code == 404
