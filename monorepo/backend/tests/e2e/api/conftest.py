from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app import bootstrap
from app.main import app
from tests.unit.application.fakes import (
    FakeEmbeddingService,
    FakeSupplierVectorRepository,
    InMemorySupplierRepository,
    InMemoryUserRepository,
)


@pytest_asyncio.fixture
async def api() -> AsyncGenerator[AsyncClient, None]:
    """Cliente HTTP con los repositorios sobreescritos por dobles en memoria.

    Evita depender de Postgres/Qdrant: ASGITransport no dispara el lifespan,
    así que inyectamos repos en memoria vía dependency_overrides. El token JWT
    sí se firma/verifica de verdad (servicio real), validando el flujo completo.
    """
    users = InMemoryUserRepository()
    suppliers = InMemorySupplierRepository()
    vectors = FakeSupplierVectorRepository()

    app.dependency_overrides[bootstrap.get_user_repo] = lambda: users
    app.dependency_overrides[bootstrap.get_supplier_repo] = lambda: suppliers
    app.dependency_overrides[bootstrap.get_supplier_vector_repo] = lambda: vectors
    app.dependency_overrides[bootstrap.get_embedding_service] = lambda: (
        FakeEmbeddingService()
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
