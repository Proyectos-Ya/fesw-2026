"""Cambios del tablero kanban hasta el aviso del otro miembro, con la pila real (HU-18, CA2).

Router, casos de uso, repositorios y Postgres reales; solo se sustituyen las claves
públicas del token y el padrón de correos.
"""

from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.db import get_session
from app.infrastructure.repositories.supplier_member_model import SupplierMemberModel
from app.infrastructure.repositories.supplier_model import SupplierModel
from app.main import app
from app.shared.datetime_utils import utc_now_naive
from tests.integration.test_milestone_calendar_repositories import _licitacion
from tests.support.api_auth import autenticar, preparar_auth


@pytest_asyncio.fixture
async def api(integration_engine: AsyncEngine) -> AsyncGenerator[AsyncClient, None]:
    async def sesion() -> AsyncGenerator[AsyncSession, None]:
        async with AsyncSession(integration_engine, expire_on_commit=False) as s:
            yield s

    app.dependency_overrides[get_session] = sesion
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        preparar_auth(app, ac)
        yield ac
    app.dependency_overrides.clear()


async def _como(api: AsyncClient, sub: str) -> UUID:
    return await autenticar(api, sub=sub, email=f"{sub}@ejemplo.cl")


async def test_cada_cambio_del_tablero_avisa_al_otro_miembro(
    api: AsyncClient, db_session: AsyncSession
):
    ana = await _como(api, "11111111-1111-4111-8111-111111111111")
    beto = await _como(api, "22222222-2222-4222-8222-222222222222")
    ahora = utc_now_naive()
    empresa = uuid4()
    db_session.add(
        SupplierModel(id=empresa, user_id=ana, rut="76.086.428-5", legal_name="Empresa SpA", created_at=ahora, updated_at=ahora)
    )
    await db_session.commit()
    for user_id, rol in ((ana, "admin"), (beto, "member")):
        db_session.add(
            SupplierMemberModel(id=uuid4(), user_id=user_id, supplier_id=empresa, role=rol, status="active", created_at=ahora, updated_at=ahora)
        )
    await db_session.commit()
    licitacion = await _licitacion(db_session)

    async def sin_leer() -> int:
        beto_token = api.claves.token(sub="22222222-2222-4222-8222-222222222222", email="22222222-2222-4222-8222-222222222222@ejemplo.cl", user_metadata={})
        r = await api.get("/notifications/unread-count", headers={"Authorization": f"Bearer {beto_token}"})
        assert r.status_code == 200, r.text
        return r.json()["count"]

    token_ana = api.claves.token(sub="11111111-1111-4111-8111-111111111111", email="11111111-1111-4111-8111-111111111111@ejemplo.cl", user_metadata={})
    token_beto = api.claves.token(sub="22222222-2222-4222-8222-222222222222", email="22222222-2222-4222-8222-222222222222@ejemplo.cl", user_metadata={})
    como_ana = {"Authorization": f"Bearer {token_ana}", "X-Workspace-Id": str(empresa)}
    como_beto = {"Authorization": f"Bearer {token_beto}", "X-Workspace-Id": str(empresa)}

    activar = await api.patch("/notifications/preferences", json={"kanban_notifications_enabled": True}, headers=como_beto)
    assert activar.status_code == 200, activar.text

    columnas = []
    for nombre in ("Por contactar", "En preparación"):
        r = await api.post("/kanban/columns", json={"name": nombre}, headers=como_ana)
        assert r.status_code == 201, r.text
        columnas.append(r.json()["id"])

    r = await api.post("/kanban/cards", json={"tender_id": str(licitacion), "column_id": columnas[0]}, headers=como_ana)
    assert r.status_code == 201, r.text
    assert await sin_leer() == 1, "el primer cambio (agregar tarjeta) no avisó"

    await db_session.execute(text("UPDATE notification SET read_at = now()"))
    await db_session.commit()
    assert await sin_leer() == 0

    r = await api.patch(f"/kanban/cards/{licitacion}", json={"column_id": columnas[1]}, headers=como_ana)
    assert r.status_code == 200, r.text
    assert await sin_leer() == 1, "el segundo cambio (mover tarjeta) no avisó"

    await db_session.execute(text("UPDATE notification SET read_at = now()"))
    await db_session.commit()
    r = await api.patch(f"/kanban/cards/{licitacion}", json={"column_id": columnas[0]}, headers=como_ana)
    assert r.status_code == 200, r.text
    assert await sin_leer() == 1, "el tercer cambio no avisó"

    # Quien hace el cambio no se avisa a sí mismo.
    token_ana_count = await api.get("/notifications/unread-count", headers={"Authorization": f"Bearer {token_ana}"})
    assert token_ana_count.json()["count"] == 0
