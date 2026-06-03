import pytest
from httpx import AsyncClient

VALID_RUT = "76086428-5"


async def _signup(api: AsyncClient, email: str) -> dict[str, str]:
    """Registra e inicia sesión; devuelve el header Authorization del usuario."""
    await api.post(
        "/auth/register",
        json={"email": email, "password": "supersecret", "full_name": email},
    )
    login = await api.post(
        "/auth/login", json={"email": email, "password": "supersecret"}
    )
    token = login.json()["access_token"]
    # Limpiamos la cookie para que cada request use solo el Bearer indicado
    api.cookies.clear()
    return {"Authorization": f"Bearer {token}"}


async def _create_supplier(api: AsyncClient, admin: dict[str, str]) -> dict:
    resp = await api.post(
        "/suppliers/",
        json={"rut": VALID_RUT, "legal_name": "Empresa SpA"},
        headers=admin,
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_create_supplier_makes_creator_admin(api: AsyncClient):
    admin = await _signup(api, "admin@example.com")
    body = await _create_supplier(api, admin)
    assert body["supplier"]["rut"] == VALID_RUT
    assert body["membership"]["role"] == "admin"
    assert body["membership"]["status"] == "active"


@pytest.mark.asyncio
async def test_full_join_and_approval_flow(api: AsyncClient):
    admin = await _signup(api, "admin@example.com")
    joiner = await _signup(api, "joiner@example.com")

    supplier = (await _create_supplier(api, admin))["supplier"]
    supplier_id = supplier["id"]

    # El segundo usuario solicita unirse por RUT
    join = await api.post("/suppliers/join", json={"rut": VALID_RUT}, headers=joiner)
    assert join.status_code == 201
    assert join.json()["status"] == "pending"
    membership_id = join.json()["id"]

    # Un no-admin no puede listar los miembros
    forbidden = await api.get(f"/suppliers/{supplier_id}/members", headers=joiner)
    assert forbidden.status_code == 403

    # El admin ve la solicitud pendiente con el filtro de estado
    pending = await api.get(
        f"/suppliers/{supplier_id}/members?status=pending", headers=admin
    )
    assert pending.status_code == 200
    assert len(pending.json()) == 1

    # El admin la aprueba
    approve = await api.post(
        f"/suppliers/{supplier_id}/members/{membership_id}/approve", headers=admin
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "active"

    # Ahora hay 2 miembros activos
    active = await api.get(
        f"/suppliers/{supplier_id}/members?status=active", headers=admin
    )
    assert len(active.json()) == 2

    # Y sin filtro también son 2 (admin + miembro)
    everyone = await api.get(f"/suppliers/{supplier_id}/members", headers=admin)
    assert len(everyone.json()) == 2


@pytest.mark.asyncio
async def test_join_unknown_rut_returns_404(api: AsyncClient):
    user = await _signup(api, "solo@example.com")
    resp = await api.post("/suppliers/join", json={"rut": VALID_RUT}, headers=user)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_user_in_supplier_cannot_join_another(api: AsyncClient):
    admin = await _signup(api, "admin@example.com")
    await _create_supplier(api, admin)
    # El admin ya pertenece a un proveedor → no puede unirse a otro
    resp = await api.post("/suppliers/join", json={"rut": VALID_RUT}, headers=admin)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_admin_rejects_request(api: AsyncClient):
    admin = await _signup(api, "admin@example.com")
    joiner = await _signup(api, "joiner@example.com")
    supplier_id = (await _create_supplier(api, admin))["supplier"]["id"]

    join = await api.post("/suppliers/join", json={"rut": VALID_RUT}, headers=joiner)
    membership_id = join.json()["id"]

    reject = await api.post(
        f"/suppliers/{supplier_id}/members/{membership_id}/reject", headers=admin
    )
    assert reject.status_code == 204

    # Tras el rechazo no quedan solicitudes pendientes
    pending = await api.get(
        f"/suppliers/{supplier_id}/members?status=pending", headers=admin
    )
    assert pending.json() == []


@pytest.mark.asyncio
async def test_user_can_see_own_membership(api: AsyncClient):
    admin = await _signup(api, "admin@example.com")
    joiner = await _signup(api, "joiner@example.com")
    await _create_supplier(api, admin)
    await api.post("/suppliers/join", json={"rut": VALID_RUT}, headers=joiner)

    # El que se unió consulta su propio estado vía /users/{id}/membership.
    # Obtiene su id desde /auth/me.
    me = await api.get("/auth/me", headers=joiner)
    joiner_id = me.json()["id"]

    resp = await api.get(f"/users/{joiner_id}/membership", headers=joiner)
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_user_without_membership_gets_404(api: AsyncClient):
    user = await _signup(api, "solo@example.com")
    me = await api.get("/auth/me", headers=user)
    user_id = me.json()["id"]

    resp = await api.get(f"/users/{user_id}/membership", headers=user)
    assert resp.status_code == 404
