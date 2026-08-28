import pytest
from httpx import AsyncClient

REGISTER = {
    "email": "ana@example.com",
    "password": "supersecret",
    "full_name": "Ana Pérez",
}


@pytest.mark.asyncio
async def test_register_returns_public_user(api: AsyncClient):
    resp = await api.post("/auth/register", json=REGISTER)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "ana@example.com"
    assert body["active"] is True
    # Nunca se expone el hash de la contraseña
    assert "hashed_password" not in body
    assert "password" not in body


@pytest.mark.asyncio
async def test_register_duplicate_returns_409(api: AsyncClient):
    await api.post("/auth/register", json=REGISTER)
    resp = await api.post("/auth/register", json=REGISTER)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_sets_cookie_and_returns_token(api: AsyncClient):
    await api.post("/auth/register", json=REGISTER)
    resp = await api.post(
        "/auth/login",
        json={"email": REGISTER["email"], "password": REGISTER["password"]},
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]
    assert "access_token" in resp.cookies


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(api: AsyncClient):
    await api.post("/auth/register", json=REGISTER)
    resp = await api.post(
        "/auth/login", json={"email": REGISTER["email"], "password": "incorrecta"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_without_session_returns_401(api: AsyncClient):
    # /auth/me es una ruta protegida sin parámetros de path
    resp = await api.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_with_cookie_session(api: AsyncClient):
    await api.post("/auth/register", json=REGISTER)
    # El login deja la cookie en el cookie jar del cliente
    await api.post(
        "/auth/login",
        json={"email": REGISTER["email"], "password": REGISTER["password"]},
    )
    resp = await api.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == REGISTER["email"]


@pytest.mark.asyncio
async def test_me_with_bearer_header(api: AsyncClient):
    await api.post("/auth/register", json=REGISTER)
    login = await api.post(
        "/auth/login",
        json={"email": REGISTER["email"], "password": REGISTER["password"]},
    )
    token = login.json()["access_token"]
    # Cliente nuevo sin cookies: solo el header Authorization (caso Swagger)
    api.cookies.clear()
    resp = await api.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == REGISTER["email"]


@pytest.mark.asyncio
async def test_logout_clears_session(api: AsyncClient):
    await api.post("/auth/register", json=REGISTER)
    await api.post(
        "/auth/login",
        json={"email": REGISTER["email"], "password": REGISTER["password"]},
    )
    await api.post("/auth/logout")
    api.cookies.clear()
    resp = await api.get("/auth/me")
    assert resp.status_code == 401
