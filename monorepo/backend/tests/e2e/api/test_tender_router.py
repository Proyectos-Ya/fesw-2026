from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.bootstrap import get_rank_tenders_use_case
from app.domain.entities.matching_result import MatchingResult
from app.domain.errors.supplier_errors import SupplierNotFoundForUser, SupplierVectorNotFound
from app.main import app


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Pruebas para GET /tenders/recomended
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_recommended_tenders_success(api: AsyncClient) -> None:
    """Valida que el endpoint retorne un listado exitoso de recomendaciones con código 200."""
    profile_id = uuid4()
    mock_results = [
        MatchingResult(
            supplier_id=profile_id,
            tender_id=uuid4(),
            similarity_score=0.90,
            final_score=0.95,
            model_version="bge-m3-v1",
        )
    ]
    mock_uc = AsyncMock()
    mock_uc.execute.return_value = mock_results
    app.dependency_overrides[get_rank_tenders_use_case] = lambda: mock_uc

    # Registrar e iniciar sesión para estar autenticado en la API
    register_data = {
        "email": "juan@example.com",
        "password": "supersecretpassword",
        "full_name": "Juan Pérez",
    }
    await api.post("/auth/register", json=register_data)
    await api.post(
        "/auth/login",
        json={"email": register_data["email"], "password": register_data["password"]},
    )

    response = await api.get(f"/tenders/recomended?profile_id={profile_id}")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["supplier_id"] == str(profile_id)
    assert data[0]["final_score"] == 0.95
    mock_uc.execute.assert_called_once_with(user_id=profile_id, force_refresh=False)


@pytest.mark.asyncio
async def test_get_recommended_tenders_supplier_not_found(api: AsyncClient) -> None:
    """Valida que si el proveedor no está asociado al usuario el endpoint retorne un código 404."""
    profile_id = uuid4()
    mock_uc = AsyncMock()
    mock_uc.execute.side_effect = SupplierNotFoundForUser(profile_id)
    app.dependency_overrides[get_rank_tenders_use_case] = lambda: mock_uc

    # Iniciar sesión
    register_data = {
        "email": "maria@example.com",
        "password": "password123",
        "full_name": "María Gómez",
    }
    await api.post("/auth/register", json=register_data)
    await api.post(
        "/auth/login",
        json={"email": register_data["email"], "password": register_data["password"]},
    )

    response = await api.get(f"/tenders/recomended?profile_id={profile_id}")

    assert response.status_code == 404
    data = response.json()
    assert "No se encontró un perfil de proveedor asociado al usuario" in data["detail"]


@pytest.mark.asyncio
async def test_get_recommended_tenders_vector_not_found(api: AsyncClient) -> None:
    """Valida que si el vector del proveedor no está en Qdrant el endpoint retorne un código 404."""
    profile_id = uuid4()
    mock_uc = AsyncMock()
    mock_uc.execute.side_effect = SupplierVectorNotFound(profile_id)
    app.dependency_overrides[get_rank_tenders_use_case] = lambda: mock_uc

    # Iniciar sesión
    register_data = {
        "email": "pedro@example.com",
        "password": "securepwd123",
        "full_name": "Pedro Díaz",
    }
    await api.post("/auth/register", json=register_data)
    await api.post(
        "/auth/login",
        json={"email": register_data["email"], "password": register_data["password"]},
    )

    response = await api.get(f"/tenders/recomended?profile_id={profile_id}")

    assert response.status_code == 404
    data = response.json()
    assert "No se encontró el vector para el proveedor" in data["detail"]


@pytest.mark.asyncio
async def test_get_recommended_tenders_unauthorized(api: AsyncClient) -> None:
    """Valida que si la petición no está autenticada retorne un código 401."""
    profile_id = uuid4()
    response = await api.get(f"/tenders/recomended?profile_id={profile_id}")
    assert response.status_code == 401
