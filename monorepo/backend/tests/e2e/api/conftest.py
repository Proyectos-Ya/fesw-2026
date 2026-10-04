from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app import bootstrap
from app.application.services.recent_ranking_registry import RecentRankingRegistry
from app.main import app
from tests.support.api_auth import preparar_auth
from tests.unit.application.fakes import (
    FakeEmailService,
    FakeEmbeddingService,
    FakeRankingImpressionLogger,
    FakeSupplierVectorRepository,
    InMemorySupplierInvitationRepository,
    InMemorySupplierMemberRepository,
    InMemorySupplierRepository,
    InMemoryUserRepository,
)


@pytest_asyncio.fixture
async def api() -> AsyncGenerator[AsyncClient, None]:
    """Cliente HTTP con los repositorios sobreescritos por dobles en memoria.

    Evita depender de Postgres/Qdrant: ASGITransport no dispara el lifespan,
    así que inyectamos repos en memoria vía dependency_overrides. El token de
    Supabase sí se firma y se verifica de verdad (`preparar_auth` solo sustituye
    de dónde salen las claves públicas), validando el flujo completo.
    """
    users = InMemoryUserRepository()
    suppliers = InMemorySupplierRepository()
    members = InMemorySupplierMemberRepository(supplier_repo=suppliers)
    invitations = InMemorySupplierInvitationRepository()
    vectors = FakeSupplierVectorRepository()
    emails = FakeEmailService()
    impresiones = FakeRankingImpressionLogger()
    # Uno por test: el de `app.state` se compartiría entre tests.
    registro = RecentRankingRegistry()

    app.dependency_overrides[bootstrap.get_user_repo] = lambda: users
    app.dependency_overrides[bootstrap.get_supplier_repo] = lambda: suppliers
    app.dependency_overrides[bootstrap.get_supplier_member_repo] = lambda: members
    app.dependency_overrides[bootstrap.get_supplier_invitation_repo] = lambda: invitations
    app.dependency_overrides[bootstrap.get_supplier_vector_repo] = lambda: vectors
    app.dependency_overrides[bootstrap.get_embedding_service] = lambda: (
        FakeEmbeddingService()
    )
    app.dependency_overrides[bootstrap.get_email_service] = lambda: emails
    # Sin estos overrides, los tests de `/tenders/recommended` intentarían escribir
    # las impresiones en la base de desarrollo.
    app.dependency_overrides[bootstrap.get_ranking_impression_logger] = lambda: impresiones
    app.dependency_overrides[bootstrap.get_ranking_registry] = lambda: registro

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        preparar_auth(app, ac)
        # Se cuelga el repositorio del cliente para los tests que necesitan
        # tocar el estado directamente (desactivar una cuenta, por ejemplo).
        ac.usuarios = users
        ac.proveedores = suppliers
        ac.miembros = members
        ac.correos = emails
        ac.rankings_registrados = impresiones
        yield ac

    app.dependency_overrides.clear()

