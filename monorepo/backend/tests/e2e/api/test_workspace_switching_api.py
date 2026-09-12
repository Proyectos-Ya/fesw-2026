import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_workspace_switching_and_dynamic_permissions(api: AsyncClient):
    # 1. Crear Usuario A y su Empresa 1
    user_a = {
        "email": "user_a@test.cl",
        "password": "password123",
        "full_name": "Usuario A",
    }
    await api.post("/auth/register", json=user_a)
    login_a = await api.post(
        "/auth/login",
        json={"email": user_a["email"], "password": user_a["password"]},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    sup_1 = await api.post(
        "/suppliers",
        json={"rut": "76.123.456-0", "legal_name": "Empresa Uno SpA"},
        headers=headers_a,
    )
    assert sup_1.status_code == 201
    empresa_1_id = sup_1.json()["id"]

    # 2. Crear Usuario B y su Empresa 2
    user_b = {
        "email": "user_b@test.cl",
        "password": "password123",
        "full_name": "Usuario B",
    }
    await api.post("/auth/register", json=user_b)
    login_b = await api.post(
        "/auth/login",
        json={"email": user_b["email"], "password": user_b["password"]},
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    sup_2 = await api.post(
        "/suppliers",
        json={"rut": "77.654.321-7", "legal_name": "Empresa Dos Ltda"},
        headers=headers_b,
    )
    assert sup_2.status_code == 201
    empresa_2_id = sup_2.json()["id"]

    # 3. Usuario B invita a Usuario A como MEMBER a Empresa 2
    inv_resp = await api.post(
        "/workspaces/invitations",
        json={
            "supplier_id": empresa_2_id,
            "email": "user_a@test.cl",
            "role": "member",
        },
        headers=headers_b,
    )
    assert inv_resp.status_code == 201
    token_inv = inv_resp.json()["token"]

    # 4. Usuario A acepta la invitación
    acc_resp = await api.post(
        "/workspaces/invitations/accept",
        json={"token": token_inv},
        headers=headers_a,
    )
    assert acc_resp.status_code == 200

    # 5. Usuario A consulta contexto inicial (Empresa 1 - ADMIN)
    api.cookies.delete("active_workspace_id")
    curr_resp = await api.get("/workspaces/current", headers=headers_a)
    assert curr_resp.status_code == 200
    curr_context = curr_resp.json()
    assert curr_context["active_supplier_id"] == empresa_1_id
    assert curr_context["role"] == "admin"
    assert curr_context["is_admin"] is True
    assert "invite_members" in curr_context["permissions"]

    # 6. Usuario A conmuta a Empresa 2 (POST /workspaces/switch)
    switch_resp = await api.post(
        "/workspaces/switch",
        json={"supplier_id": empresa_2_id},
        headers=headers_a,
    )
    assert switch_resp.status_code == 200
    switched_context = switch_resp.json()
    assert switched_context["active_supplier_id"] == empresa_2_id
    assert switched_context["role"] == "member"
    assert switched_context["is_admin"] is False
    assert "invite_members" not in switched_context["permissions"]
    assert "view_matches" in switched_context["permissions"]

    # Cookie active_workspace_id debe estar en la respuesta
    assert "active_workspace_id" in switch_resp.cookies

    # 7. Intentar invitar miembros mientras opera en Empresa 2 (como MEMBER) debe fallar con 403
    fail_inv = await api.post(
        "/workspaces/invitations",
        json={
            "supplier_id": empresa_2_id,
            "email": "otro@amigo.cl",
            "role": "member",
        },
        headers=headers_a,
    )
    assert fail_inv.status_code == 403

    # 8. Usuario A vuelve a conmutar a Empresa 1
    switch_back = await api.post(
        "/workspaces/switch",
        json={"supplier_id": empresa_1_id},
        headers=headers_a,
    )
    assert switch_back.status_code == 200
    assert switch_back.json()["role"] == "admin"
    assert "invite_members" in switch_back.json()["permissions"]

    # Ahora sí puede invitar en Empresa 1 porque volvió a ser ADMIN
    ok_inv = await api.post(
        "/workspaces/invitations",
        json={
            "supplier_id": empresa_1_id,
            "email": "otro@amigo.cl",
            "role": "member",
        },
        headers=headers_a,
    )
    assert ok_inv.status_code == 201


@pytest.mark.asyncio
async def test_switch_unauthorized_workspace_fails(api: AsyncClient):
    user_a = {
        "email": "solo@empresa.cl",
        "password": "password123",
        "full_name": "Solo",
    }
    await api.post("/auth/register", json=user_a)
    login_a = await api.post(
        "/auth/login",
        json={"email": user_a["email"], "password": user_a["password"]},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # Intentar cambiarse a un UUID de empresa al que no pertenece -> 403
    from uuid import uuid4

    fake_id = str(uuid4())
    resp = await api.post(
        "/workspaces/switch",
        json={"supplier_id": fake_id},
        headers=headers_a,
    )
    # 404 si no existe la empresa, o 403 si no pertenece
    assert resp.status_code in (403, 404)
