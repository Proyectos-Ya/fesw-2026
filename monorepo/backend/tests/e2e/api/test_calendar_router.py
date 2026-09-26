"""Pruebas e2e de /calendar sobre la aplicación real (HU-16).

Verifican el cableado y la autenticación, y que con Google Calendar sin
configurar la app responde bien en vez de fallar.
"""

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app import bootstrap
from app.main import app
from tests.support.api_auth import autenticar, preparar_auth
from tests.unit.application.fakes import (
    FakeEmbeddingService,
    FakeSupplierVectorRepository,
    InMemorySupplierRepository,
    InMemoryUserRepository,
)
from tests.unit.application.milestone_fakes import InMemoryCalendarConnectionRepository


@pytest_asyncio.fixture
async def api() -> AsyncGenerator[AsyncClient, None]:
    users = InMemoryUserRepository()
    app.dependency_overrides[bootstrap.get_user_repo] = lambda: users
    app.dependency_overrides[bootstrap.get_supplier_repo] = lambda: InMemorySupplierRepository()
    app.dependency_overrides[bootstrap.get_supplier_vector_repo] = lambda: FakeSupplierVectorRepository()
    app.dependency_overrides[bootstrap.get_embedding_service] = lambda: FakeEmbeddingService()
    conexiones = InMemoryCalendarConnectionRepository()
    app.dependency_overrides[bootstrap.get_calendar_connection_repo] = lambda: conexiones
    # Independiente del .env local: como si Google Calendar no estuviera configurado.
    app.dependency_overrides[bootstrap.get_calendar_providers] = lambda: {}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        preparar_auth(app, ac)
        yield ac
    app.dependency_overrides.clear()


async def test_sin_sesion_no_hay_acceso(api: AsyncClient):
    assert (await api.get("/calendar/connections")).status_code == 401
    assert (await api.post("/calendar/google/callback", json={"code": "c", "state": "s"})).status_code == 401


async def test_sin_credenciales_de_google_no_hay_proveedores(api: AsyncClient):
    await autenticar(api, email="calendario@example.com", full_name="Representante")

    assert (await api.get("/calendar/connections")).json() == []


async def test_sin_credenciales_de_google_autorizar_responde_503(api: AsyncClient):
    await autenticar(api, email="calendario@example.com", full_name="Representante")

    respuesta = await api.post(
        "/calendar/google/authorize",
        json={"tender_id": str(uuid4()), "milestone_ids": [str(uuid4())]},
    )

    assert respuesta.status_code == 503
    assert "Google Calendar" in respuesta.json()["detail"]
