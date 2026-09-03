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
    # Sin limpiar el cliente a mano: si el logout no borra la cookie de verdad,
    # httpx la sigue enviando y /auth/me respondería 200.
    resp = await api.get("/auth/me")
    assert "access_token" not in api.cookies
    assert resp.status_code == 401


def _atributos_set_cookie(header: str) -> dict[str, str]:
    """Atributos de un header Set-Cookie, en minúsculas y sin el par nombre=valor."""
    partes = [p.strip() for p in header.split(";")[1:]]
    atributos: dict[str, str] = {}
    for parte in partes:
        clave, _, valor = parte.partition("=")
        atributos[clave.lower()] = valor.lower()
    return atributos


@pytest.mark.asyncio
async def test_logout_borra_la_cookie_con_los_mismos_atributos_del_login(
    api: AsyncClient,
):
    """El Set-Cookie de borrado debe repetir Path/Secure/SameSite/HttpOnly del login.

    Si no coinciden, el navegador ignora el borrado y la sesión sobrevive al
    logout. En producción el frontend (Vercel) y el backend (Railway) están en
    dominios distintos, así que la cookie viaja como SameSite=None; Secure: un
    borrado con los valores por defecto de Starlette (Lax, sin Secure) se
    descarta en silencio y el backend igual responde 204.
    """
    await api.post("/auth/register", json=REGISTER)
    login = await api.post(
        "/auth/login",
        json={"email": REGISTER["email"], "password": REGISTER["password"]},
    )
    logout = await api.post("/auth/logout")

    set_cookie_login = _atributos_set_cookie(login.headers["set-cookie"])
    set_cookie_logout = _atributos_set_cookie(logout.headers["set-cookie"])

    for atributo in ("path", "samesite", "secure", "httponly"):
        assert set_cookie_login.get(atributo) == set_cookie_logout.get(atributo), (
            f"El atributo {atributo!r} difiere entre login y logout: "
            f"{set_cookie_login.get(atributo)!r} vs {set_cookie_logout.get(atributo)!r}"
        )
