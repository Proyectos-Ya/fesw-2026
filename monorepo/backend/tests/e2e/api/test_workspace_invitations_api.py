import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_full_workspace_invitation_and_acceptance_flow(api: AsyncClient):
    # 1. Registrar Usuario A (Dueño/Admin)
    admin_data = {
        "email": "admin_empresa@demo.cl",
        "password": "password123",
        "full_name": "Admin Empresa",
    }
    resp_reg_a = await api.post("/auth/register", json=admin_data)
    assert resp_reg_a.status_code == 201

    resp_login_a = await api.post(
        "/auth/login",
        json={"email": admin_data["email"], "password": admin_data["password"]},
    )
    assert resp_login_a.status_code == 200
    token_a = resp_login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Crear empresa para Usuario A
    supplier_payload = {
        "rut": "76.123.456-0",
        "legal_name": "Empresa Principal SpA",
        "trade_name": "Principal",
        "description": "Empresa constructora con amplia experiencia en licitaciones del sector público.",
        "regions": ["Metropolitana"],
        "sectors": ["Construcción"],
        "years_experience": 5,
        "num_employees": 25,
    }
    resp_sup = await api.post("/suppliers", json=supplier_payload, headers=headers_a)
    assert resp_sup.status_code == 201
    supplier_id = resp_sup.json()["id"]

    # 2. Usuario A crea una invitación para socio@demo.cl
    invite_payload = {
        "supplier_id": supplier_id,
        "email": "socio@demo.cl",
        "role": "member",
    }
    resp_inv = await api.post(
        "/workspaces/invitations", json=invite_payload, headers=headers_a
    )
    assert resp_inv.status_code == 201
    invitation = resp_inv.json()
    token_invitation = invitation["token"]
    assert invitation["email"] == "socio@demo.cl"
    assert invitation["status"] == "pending"

    # 3. Consultar datos de la invitación por token
    resp_verify = await api.get(
        f"/workspaces/invitations/verify?token={token_invitation}"
    )
    assert resp_verify.status_code == 200
    verify_data = resp_verify.json()
    assert verify_data["supplier_id"] == supplier_id
    assert verify_data["supplier_name"] == "Principal"
    assert verify_data["email"] == "socio@demo.cl"

    # 4. Registrar e iniciar sesión como Usuario B (el invitado)
    user_b_data = {
        "email": "socio@demo.cl",
        "password": "password123",
        "full_name": "Socio Colaborador",
    }
    resp_reg_b = await api.post("/auth/register", json=user_b_data)
    assert resp_reg_b.status_code == 201

    resp_login_b = await api.post(
        "/auth/login",
        json={"email": user_b_data["email"], "password": user_b_data["password"]},
    )
    assert resp_login_b.status_code == 200
    token_b = resp_login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Usuario B consulta sus invitaciones pendientes
    resp_my_inv = await api.get("/workspaces/invitations/me", headers=headers_b)
    assert resp_my_inv.status_code == 200
    assert len(resp_my_inv.json()) >= 1

    # 5. Usuario B acepta la invitación con su cuenta existente (CA-1)
    resp_accept = await api.post(
        "/workspaces/invitations/accept",
        json={"token": token_invitation},
        headers=headers_b,
    )
    assert resp_accept.status_code == 200
    accepted_data = resp_accept.json()
    assert accepted_data["supplier_id"] == supplier_id
    assert accepted_data["role"] == "member"
    assert accepted_data["status"] == "active"

    # 6. Usuario B consulta sus workspaces y verifica que pertenece a la empresa
    resp_workspaces = await api.get("/workspaces", headers=headers_b)
    assert resp_workspaces.status_code == 200
    workspaces = resp_workspaces.json()
    assert len(workspaces) >= 1
    matched = next((w for w in workspaces if w["supplier_id"] == supplier_id), None)
    assert matched is not None
    assert matched["legal_name"] == "Empresa Principal SpA"
    assert matched["role"] == "member"

    # 7. Intentar aceptar nuevamente la misma invitación devuelve error 400
    resp_reaccept = await api.post(
        "/workspaces/invitations/accept",
        json={"token": token_invitation},
        headers=headers_b,
    )
    assert resp_reaccept.status_code == 400


@pytest.mark.asyncio
async def test_accept_invitation_email_mismatch_fails_e2e(api: AsyncClient):
    # Registrar Admin
    admin_data = {
        "email": "owner@corp.cl",
        "password": "password123",
        "full_name": "Corp Owner",
    }
    await api.post("/auth/register", json=admin_data)
    login_a = await api.post(
        "/auth/login",
        json={"email": admin_data["email"], "password": admin_data["password"]},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # Crear empresa
    sup_resp = await api.post(
        "/suppliers",
        json={
            "rut": "77.654.321-7",
            "legal_name": "Corp SpA",
            "description": "Corporación especializada en servicios de consultoría y asesoría empresarial.",
            "regions": ["Valparaíso"],
            "sectors": ["Consultoría"],
            "years_experience": 10,
            "num_employees": 40,
        },
        headers=headers_a,
    )
    assert sup_resp.status_code == 201
    supplier_id = sup_resp.json()["id"]


    # Invitar a alguien@corp.cl
    inv_resp = await api.post(
        "/workspaces/invitations",
        json={"supplier_id": supplier_id, "email": "alguien@corp.cl", "role": "member"},
        headers=headers_a,
    )
    token = inv_resp.json()["token"]

    # Registrar usuario C con otro correo
    user_c_data = {
        "email": "intruso@externo.cl",
        "password": "password123",
        "full_name": "Intruso",
    }
    await api.post("/auth/register", json=user_c_data)
    login_c = await api.post(
        "/auth/login",
        json={"email": user_c_data["email"], "password": user_c_data["password"]},
    )
    headers_c = {"Authorization": f"Bearer {login_c.json()['access_token']}"}

    # Intentar aceptar invitación ajena -> 403 Forbidden
    resp_accept = await api.post(
        "/workspaces/invitations/accept",
        json={"token": token},
        headers=headers_c,
    )
    assert resp_accept.status_code == 403
