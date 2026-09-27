import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_full_workspace_invitation_and_acceptance_flow(api: AsyncClient):
    # 1. Registrar Usuario A (Dueño/Admin) vía Supabase Auth
    sub_a = "11111111-1111-4111-8111-111111111111"
    api.directorio_de_identidad.confirmar(sub_a)
    token_a = api.claves.token(
        sub=sub_a,
        email="admin_empresa@demo.cl",
        user_metadata={"full_name": "Admin Empresa"},
    )
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
    sub_b = "22222222-2222-4222-8222-222222222222"
    api.directorio_de_identidad.confirmar(sub_b)
    token_b = api.claves.token(
        sub=sub_b,
        email="socio@demo.cl",
        user_metadata={"full_name": "Socio Colaborador"},
    )
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
    sub_owner = "33333333-3333-4333-8333-333333333333"
    api.directorio_de_identidad.confirmar(sub_owner)
    token_a = api.claves.token(
        sub=sub_owner,
        email="owner@corp.cl",
        user_metadata={"full_name": "Corp Owner"},
    )
    headers_a = {"Authorization": f"Bearer {token_a}"}

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
    sub_c = "44444444-4444-4444-8444-444444444444"
    api.directorio_de_identidad.confirmar(sub_c)
    token_c = api.claves.token(
        sub=sub_c,
        email="intruso@externo.cl",
        user_metadata={"full_name": "Intruso"},
    )
    headers_c = {"Authorization": f"Bearer {token_c}"}

    # Intentar aceptar invitación ajena -> 403 Forbidden
    resp_accept = await api.post(
        "/workspaces/invitations/accept",
        json={"token": token},
        headers=headers_c,
    )
    assert resp_accept.status_code == 403


@pytest.mark.asyncio
async def test_hu12_email_dispatch_duplicates_team_listing_and_suppliers_me(
    api: AsyncClient,
):
    # 1. Crear Admin y su empresa
    sub_admin = "55555555-5555-4555-8555-555555555555"
    api.directorio_de_identidad.confirmar(sub_admin)
    token_admin = api.claves.token(
        sub=sub_admin,
        email="admin_hu12@empresa.cl",
        user_metadata={"full_name": "Admin HU12"},
    )
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    sup_resp = await api.post(
        "/suppliers",
        json={
            "rut": "76.123.456-0",
            "legal_name": "Ingeniería Austral SpA",
            "trade_name": "Austral",
            "description": "Servicios de ingeniería estructural y obras civiles en todo Chile.",
            "regions": ["Metropolitana"],
            "sectors": ["Construcción"],
            "years_experience": 6,
            "num_employees": 20,
        },
        headers=headers_admin,
    )
    assert sup_resp.status_code == 201
    supplier_id = sup_resp.json()["id"]

    # 2. Enviar invitación -> verifica despacho de correo en BackgroundTasks (CA2)
    inv_resp = await api.post(
        "/workspaces/invitations",
        json={
            "supplier_id": supplier_id,
            "email": "rep@austral.cl",
            "role": "member",
        },
        headers=headers_admin,
    )
    assert inv_resp.status_code == 201
    invitation = inv_resp.json()
    assert len(api.correos.sent) == 1
    sent_msg = api.correos.sent[0]
    assert sent_msg.to == "rep@austral.cl"
    assert "Austral" in sent_msg.subject
    assert invitation["token"] in sent_msg.text_body
    assert invitation["token"] in sent_msg.html_body

    # 3. Intentar enviar invitación duplicada mientras está pendiente -> 409 Conflict (CA3)
    dup_resp = await api.post(
        "/workspaces/invitations",
        json={
            "supplier_id": supplier_id,
            "email": "REP@austral.cl",
            "role": "member",
        },
        headers=headers_admin,
    )
    assert dup_resp.status_code == 409

    # 4. Admin consulta listado de invitaciones pendientes de la empresa (CA1, CA2)
    pending_list_resp = await api.get(
        f"/workspaces/{supplier_id}/invitations",
        headers=headers_admin,
    )
    assert pending_list_resp.status_code == 200
    pending_list = pending_list_resp.json()
    assert len(pending_list) == 1
    assert pending_list[0]["email"] == "rep@austral.cl"

    # 5. Invitado inicia sesión, ve nombre de empresa en /invitations/me (CA4, CA5) y acepta (CA6)
    sub_rep = "66666666-6666-4666-8666-666666666666"
    api.directorio_de_identidad.confirmar(sub_rep)
    token_rep = api.claves.token(
        sub=sub_rep,
        email="rep@austral.cl",
        user_metadata={"full_name": "Representante Austral"},
    )
    headers_rep = {"Authorization": f"Bearer {token_rep}"}

    my_inv_resp = await api.get("/workspaces/invitations/me", headers=headers_rep)
    assert my_inv_resp.status_code == 200
    my_invs = my_inv_resp.json()
    assert len(my_invs) == 1
    assert my_invs[0]["supplier_name"] == "Austral"
    assert my_invs[0]["supplier_rut"] == "76.123.456-0"

    acc_resp = await api.post(
        "/workspaces/invitations/accept",
        json={"token": invitation["token"]},
        headers=headers_rep,
    )
    assert acc_resp.status_code == 200

    # 6. Representante sin empresa propia consulta GET /suppliers/me y recibe la empresa del workspace (CA6)
    me_sup_resp = await api.get("/suppliers/me", headers=headers_rep)
    assert me_sup_resp.status_code == 200
    assert me_sup_resp.json()["id"] == supplier_id

    # 7. Intentar volver a invitar a quien ya es miembro activo -> 409 Conflict (CA3)
    already_member_resp = await api.post(
        "/workspaces/invitations",
        json={
            "supplier_id": supplier_id,
            "email": "rep@austral.cl",
            "role": "member",
        },
        headers=headers_admin,
    )
    assert already_member_resp.status_code == 409

    # 8. Listar miembros actuales del equipo muestra tanto al Admin como al nuevo Representante (CA1)
    members_resp = await api.get(
        f"/workspaces/{supplier_id}/members",
        headers=headers_admin,
    )
    assert members_resp.status_code == 200
    team_members = members_resp.json()
    emails_in_team = {m["email"] for m in team_members}
    assert "admin_hu12@empresa.cl" in emails_in_team
    assert "rep@austral.cl" in emails_in_team


@pytest.mark.asyncio
async def test_hu12_cancel_and_reject_invitation_flows(api: AsyncClient):
    sub_admin = "77777777-7777-4777-8777-777777777777"
    api.directorio_de_identidad.confirmar(sub_admin)
    token_admin = api.claves.token(
        sub=sub_admin,
        email="admin_cancel@empresa.cl",
        user_metadata={"full_name": "Admin Cancel"},
    )
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    sup_resp = await api.post(
        "/suppliers",
        json={
            "rut": "77.654.321-7",
            "legal_name": "Empresa Cancelaciones SpA",
            "description": "Empresa dedicada a suministros industriales y equipamiento técnico.",
            "regions": ["Metropolitana"],
            "sectors": ["Construcción"],
            "years_experience": 4,
            "num_employees": 12,
        },
        headers=headers_admin,
    )
    assert sup_resp.status_code == 201
    supplier_id = sup_resp.json()["id"]

    # Crear invitación 1 para probar cancelación por Admin (CA7, CA8)
    inv1_resp = await api.post(
        "/workspaces/invitations",
        json={
            "supplier_id": supplier_id,
            "email": "cancelado@empresa.cl",
            "role": "member",
        },
        headers=headers_admin,
    )
    assert inv1_resp.status_code == 201
    inv1 = inv1_resp.json()

    # Admin cancela la invitación pendiente (CA7)
    del_resp = await api.delete(
        f"/workspaces/invitations/{inv1['id']}",
        headers=headers_admin,
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "cancelled"

    # Destinatario intenta ver o aceptar la invitación cancelada -> invalidación inmediata (CA8)
    sub_guest1 = "88888888-8888-4888-8888-888888888888"
    api.directorio_de_identidad.confirmar(sub_guest1)
    token_guest1 = api.claves.token(
        sub=sub_guest1,
        email="cancelado@empresa.cl",
        user_metadata={"full_name": "Invitado Cancelado"},
    )
    headers_guest1 = {"Authorization": f"Bearer {token_guest1}"}

    verify_cancelled = await api.get(
        f"/workspaces/invitations/verify?token={inv1['token']}"
    )
    assert verify_cancelled.status_code == 410

    accept_cancelled = await api.post(
        "/workspaces/invitations/accept",
        json={"token": inv1["token"]},
        headers=headers_guest1,
    )
    assert accept_cancelled.status_code == 400

    # Crear invitación 2 para probar rechazo por el destinatario (CA4)
    inv2_resp = await api.post(
        "/workspaces/invitations",
        json={
            "supplier_id": supplier_id,
            "email": "rechaza@empresa.cl",
            "role": "member",
        },
        headers=headers_admin,
    )
    assert inv2_resp.status_code == 201
    inv2 = inv2_resp.json()

    sub_guest2 = "99999999-9999-4999-8999-999999999999"
    api.directorio_de_identidad.confirmar(sub_guest2)
    token_guest2 = api.claves.token(
        sub=sub_guest2,
        email="rechaza@empresa.cl",
        user_metadata={"full_name": "Invitado Rechaza"},
    )
    headers_guest2 = {"Authorization": f"Bearer {token_guest2}"}

    reject_resp = await api.post(
        "/workspaces/invitations/reject",
        json={"token": inv2["token"]},
        headers=headers_guest2,
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"

    # Ya no aparece en /invitations/me del invitado
    me_after_reject = await api.get(
        "/workspaces/invitations/me", headers=headers_guest2
    )
    assert me_after_reject.status_code == 200
    assert me_after_reject.json() == []

    # Admin aún la ve en /workspaces/{supplier_id}/invitations con estado "rejected"
    admin_invs = await api.get(
        f"/workspaces/{supplier_id}/invitations",
        headers=headers_admin,
    )
    assert admin_invs.status_code == 200
    assert len(admin_invs.json()) == 1
    assert admin_invs.json()[0]["id"] == inv2["id"]
    assert admin_invs.json()[0]["status"] == "rejected"

    # Admin confirma lectura / descarta la invitación rechazada
    dismiss_resp = await api.delete(
        f"/workspaces/invitations/{inv2['id']}",
        headers=headers_admin,
    )
    assert dismiss_resp.status_code == 200
    assert dismiss_resp.json()["status"] == "cancelled"

    admin_invs_after = await api.get(
        f"/workspaces/{supplier_id}/invitations",
        headers=headers_admin,
    )
    assert admin_invs_after.status_code == 200
    assert admin_invs_after.json() == []

