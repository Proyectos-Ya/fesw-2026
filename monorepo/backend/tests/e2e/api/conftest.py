from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.application.services.attachment_deleted_listener import (
    NoopAttachmentDeletedListener,
)
from app.application.services.attachment_stored_listener import (
    NoopAttachmentStoredListener,
)
from app.application.services.recent_ranking_registry import RecentRankingRegistry
from app.bootstrap.attachments import (
    get_attachment_deleted_listener,
    get_attachment_stored_listener,
)
from app.bootstrap.ranking_telemetry import get_ranking_impression_logger
from app.bootstrap.repositories import (
    get_supplier_invitation_repo,
    get_supplier_member_repo,
    get_supplier_repo,
    get_user_repo,
)
from app.bootstrap.services import (
    get_attachment_storage,
    get_email_service,
    get_embedding_service,
    get_ranking_registry,
    get_supplier_vector_repo,
)
from app.main import app
from tests.support.api_auth import preparar_auth
from tests.unit.application.attachment_file_fakes import FakeAttachmentStorage
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
    storage = FakeAttachmentStorage()
    # Uno por test: el de `app.state` se compartiría entre tests.
    registro = RecentRankingRegistry()

    app.dependency_overrides[get_user_repo] = lambda: users
    app.dependency_overrides[get_supplier_repo] = lambda: suppliers
    app.dependency_overrides[get_supplier_member_repo] = lambda: members
    app.dependency_overrides[get_supplier_invitation_repo] = lambda: invitations
    app.dependency_overrides[get_supplier_vector_repo] = lambda: vectors
    app.dependency_overrides[get_embedding_service] = lambda: (
        FakeEmbeddingService()
    )
    app.dependency_overrides[get_email_service] = lambda: emails
    app.dependency_overrides[get_attachment_storage] = lambda: storage
    # Sin estos overrides, los tests de `/tenders/recommended` intentarían escribir
    # las impresiones en la base de desarrollo.
    app.dependency_overrides[get_ranking_impression_logger] = lambda: impresiones
    app.dependency_overrides[get_ranking_registry] = lambda: registro
    # Sin estos, `complete` y `DELETE` de un anexo abrirían su propia sesión contra la
    # base del `.env`: la promoción de la decisión 6 no usa la sesión de la petición.
    app.dependency_overrides[get_attachment_stored_listener] = lambda: (
        NoopAttachmentStoredListener()
    )
    app.dependency_overrides[get_attachment_deleted_listener] = lambda: (
        NoopAttachmentDeletedListener()
    )

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
        ac.storage = storage
        yield ac

    app.dependency_overrides.clear()

