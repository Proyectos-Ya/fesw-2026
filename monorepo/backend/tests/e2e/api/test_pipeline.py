"""
Pruebas e2e del pipeline de proveedor: creación de perfil e indexación en Qdrant,
y consulta por ID. Usa repositorios en memoria (sin BD ni Qdrant real).
"""

from uuid import uuid4

import pytest_asyncio
from httpx import AsyncClient

VALID_SUPPLIER = {
    "rut": "76086428-5",
    "legal_name": "Constructora Demo SpA",
    "description": "Empresa con experiencia en obras civiles.",
    "sectors": ["Construcción"],
    "keywords": ["obras", "edificación"],
    "years_experience": 5,
    "num_employees": 20,
}


@pytest_asyncio.fixture(autouse=True)
async def _session(api: AsyncClient) -> None:
    """Las rutas de /suppliers exigen sesión: registra e inicia sesión antes
    de cada prueba; la cookie httpOnly queda guardada en el cliente."""
    credentials = {"email": "pipeline@example.com", "password": "supersecret"}
    await api.post("/auth/register", json={**credentials, "full_name": "Pipeline Test"})
    await api.post("/auth/login", json=credentials)


# ---------------------------------------------------------------------------
# POST /suppliers/
# ---------------------------------------------------------------------------


async def test_crear_proveedor_retorna_201(api: AsyncClient) -> None:
    """Crear un proveedor con datos válidos retorna 201 y los datos persistidos."""
    response = await api.post("/suppliers", json=VALID_SUPPLIER)

    assert response.status_code == 201
    data = response.json()
    assert data["rut"] == VALID_SUPPLIER["rut"]
    assert data["legal_name"] == VALID_SUPPLIER["legal_name"]
    assert "id" in data


async def test_crear_proveedor_indexa_en_qdrant(api: AsyncClient) -> None:
    """Crear un proveedor también registra su vector en el repositorio vectorial."""
    from app.bootstrap import get_supplier_vector_repo
    from app.main import app

    captured_vector_repo = None

    original = app.dependency_overrides.get(get_supplier_vector_repo)

    def capture_vector_repo():
        from tests.unit.application.fakes import FakeSupplierVectorRepository

        repo = FakeSupplierVectorRepository()
        nonlocal captured_vector_repo
        captured_vector_repo = repo
        return repo

    app.dependency_overrides[get_supplier_vector_repo] = capture_vector_repo

    response = await api.post("/suppliers", json=VALID_SUPPLIER)
    supplier_id = response.json()["id"]

    assert response.status_code == 201
    assert captured_vector_repo is not None
    assert len(captured_vector_repo.upserts) == 1
    assert str(captured_vector_repo.upserts[0]) == supplier_id

    if original:
        app.dependency_overrides[get_supplier_vector_repo] = original
    else:
        app.dependency_overrides.pop(get_supplier_vector_repo, None)


async def test_crear_proveedor_rut_duplicado_retorna_409(api: AsyncClient) -> None:
    """Registrar el mismo RUT dos veces retorna 409 Conflict."""
    await api.post("/suppliers", json=VALID_SUPPLIER)
    response = await api.post("/suppliers", json=VALID_SUPPLIER)

    assert response.status_code == 409


async def test_crear_proveedor_rut_invalido_retorna_400(api: AsyncClient) -> None:
    """Un RUT con dígito verificador incorrecto retorna 400 Bad Request."""
    payload = {**VALID_SUPPLIER, "rut": "76086428-0"}
    response = await api.post("/suppliers", json=payload)

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /suppliers/{supplier_id}
# ---------------------------------------------------------------------------


async def test_obtener_proveedor_existente_retorna_200(api: AsyncClient) -> None:
    """Consultar un proveedor recién creado por su ID retorna 200 con los datos."""
    created = await api.post("/suppliers", json=VALID_SUPPLIER)
    supplier_id = created.json()["id"]

    response = await api.get(f"/suppliers/{supplier_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == supplier_id
    assert data["rut"] == VALID_SUPPLIER["rut"]


async def test_obtener_proveedor_inexistente_retorna_404(api: AsyncClient) -> None:
    """Consultar un UUID que no existe retorna 404 Not Found."""
    response = await api.get(f"/suppliers/{uuid4()}")

    assert response.status_code == 404
