"""
Pruebas e2e del router /suppliers.

Todas las rutas requieren sesión iniciada (cookie httpOnly de login).
GET /suppliers/me devuelve la empresa del usuario autenticado o 404.
"""
import pytest
from httpx import AsyncClient

REGISTER = {
    "email": "dueno@example.com",
    "password": "supersecret",
    "full_name": "Dueño Empresa",
}

SUPPLIER = {
    "rut": "76086428-5",
    "legal_name": "Constructora Norte SpA",
}


async def _login(api: AsyncClient) -> None:
    """Registra e inicia sesión; la cookie queda en el cliente."""
    await api.post("/auth/register", json=REGISTER)
    resp = await api.post(
        "/auth/login",
        json={"email": REGISTER["email"], "password": REGISTER["password"]},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_supplier_without_session_returns_401(api: AsyncClient):
    resp = await api.post("/suppliers/", json=SUPPLIER)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_supplier_me_without_session_returns_401(api: AsyncClient):
    resp = await api.get("/suppliers/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_supplier_associates_logged_user(api: AsyncClient):
    await _login(api)

    resp = await api.post("/suppliers/", json=SUPPLIER)
    assert resp.status_code == 201

    me = await api.get("/auth/me")
    assert resp.json()["user_id"] == me.json()["id"]


@pytest.mark.asyncio
async def test_create_second_supplier_for_same_user_returns_409(api: AsyncClient):
    await _login(api)
    first = await api.post("/suppliers/", json=SUPPLIER)
    assert first.status_code == 201

    resp = await api.post(
        "/suppliers/", json={"rut": "77777777-7", "legal_name": "Otra Empresa SpA"}
    )
    assert resp.status_code == 409
    assert "empresa" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_supplier_me_returns_404_without_company(api: AsyncClient):
    await _login(api)

    resp = await api.get("/suppliers/me")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_supplier_me_without_session_returns_401(api: AsyncClient):
    resp = await api.patch("/suppliers/me", json={"legal_name": "Nueva SpA"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_supplier_me_without_company_returns_404(api: AsyncClient):
    await _login(api)
    resp = await api.patch("/suppliers/me", json={"legal_name": "Nueva SpA"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_supplier_me_edits_own_company(api: AsyncClient):
    await _login(api)
    await api.post("/suppliers/", json=SUPPLIER)

    resp = await api.patch(
        "/suppliers/me",
        json={"legal_name": "Constructora Renovada SpA", "num_employees": 50},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["legal_name"] == "Constructora Renovada SpA"
    assert body["num_employees"] == 50
    # El RUT no cambia: no es parte del schema de edición
    assert body["rut"] == SUPPLIER["rut"]


@pytest.mark.asyncio
async def test_get_supplier_me_returns_own_company(api: AsyncClient):
    await _login(api)
    created = await api.post("/suppliers/", json=SUPPLIER)
    assert created.status_code == 201

    resp = await api.get("/suppliers/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == created.json()["id"]
    assert body["rut"] == SUPPLIER["rut"]
