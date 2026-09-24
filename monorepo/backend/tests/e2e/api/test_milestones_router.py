"""Pruebas e2e de /tenders/{id}/milestones sobre la aplicación real (HU-16).

Los repositorios y la IA son dobles en memoria; la autenticación de Supabase se
verifica de verdad.
"""

from collections.abc import AsyncGenerator
from datetime import timedelta
from uuid import UUID, uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app import bootstrap
from app.application.services.milestone_extraction_ai_service import ExtractedMilestone
from app.application.use_cases.milestones.extract_tender_milestones import (
    ExtractTenderMilestonesUseCase,
)
from app.application.use_cases.milestones.get_tender_milestones import (
    GetTenderMilestonesUseCase,
)
from app.domain.entities.tender import Tender
from app.domain.entities.tender_chat import TenderChatDocument
from app.main import app
from app.shared.datetime_utils import utc_now_naive
from tests.support.api_auth import autenticar, preparar_auth
from tests.unit.application.fakes import (
    FakeEmbeddingService,
    FakeSupplierVectorRepository,
    InMemorySupplierRepository,
    InMemoryTenderChatRepository,
    InMemoryTenderRepository,
    InMemoryUserRepository,
)
from tests.unit.application.milestone_fakes import (
    FakeMilestoneExtractionAIService,
    InMemoryCalendarEventLinkRepository,
    InMemoryTenderMilestoneRepository,
)


class Dobles:
    def __init__(self) -> None:
        self.users = InMemoryUserRepository()
        self.tenders = InMemoryTenderRepository()
        self.chat = InMemoryTenderChatRepository()
        self.milestones = InMemoryTenderMilestoneRepository()
        self.links = InMemoryCalendarEventLinkRepository()
        self.ai = FakeMilestoneExtractionAIService(
            [
                ExtractedMilestone(
                    kind="visita_tecnica",
                    title="Visita técnica obligatoria",
                    fecha="2030-10-20",
                    hora="15:00",
                    texto_original="a las 15:00 del día 20",
                    documento="bases.pdf",
                )
            ]
        )
        ahora = utc_now_naive()
        self.tender = Tender(
            code="COT-HU16",
            name="Reparación de techumbre",
            status_id=1,
            published_at=ahora - timedelta(days=1),
            closing_at=ahora + timedelta(days=20),
            last_change_at=ahora,
            buyer_rut="61.980.170-9",
            buyer_unit="Operaciones",
        )
        self.tenders.tenders[self.tender.id] = self.tender


@pytest_asyncio.fixture
async def dobles() -> Dobles:
    return Dobles()


@pytest_asyncio.fixture
async def api(dobles: Dobles) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[bootstrap.get_user_repo] = lambda: dobles.users
    app.dependency_overrides[bootstrap.get_supplier_repo] = lambda: InMemorySupplierRepository()
    app.dependency_overrides[bootstrap.get_supplier_vector_repo] = lambda: FakeSupplierVectorRepository()
    app.dependency_overrides[bootstrap.get_embedding_service] = lambda: FakeEmbeddingService()
    app.dependency_overrides[bootstrap.get_tender_milestones_use_case] = lambda: (
        GetTenderMilestonesUseCase(
            tenders=dobles.tenders,
            milestones=dobles.milestones,
            event_links=dobles.links,
            chat=dobles.chat,
        )
    )
    app.dependency_overrides[bootstrap.get_extract_tender_milestones_use_case] = lambda: (
        ExtractTenderMilestonesUseCase(
            tenders=dobles.tenders,
            milestones=dobles.milestones,
            event_links=dobles.links,
            chat=dobles.chat,
            ai=dobles.ai,
        )
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        preparar_auth(app, ac)
        yield ac
    app.dependency_overrides.clear()


async def _login(api: AsyncClient) -> UUID:
    return UUID(str(await autenticar(api, email="hitos@example.com", full_name="Representante")))


async def test_sin_sesion_no_hay_acceso(api: AsyncClient, dobles: Dobles):
    ruta = f"/tenders/{dobles.tender.id}/milestones"

    assert (await api.get(ruta)).status_code == 401
    assert (await api.post(f"{ruta}/extract")).status_code == 401


async def test_flujo_completo_de_consulta_y_extraccion(api: AsyncClient, dobles: Dobles):
    user_id = await _login(api)
    ruta = f"/tenders/{dobles.tender.id}/milestones"

    inicial = (await api.get(ruta)).json()
    assert [m["kind"] for m in inicial["milestones"]] == ["publicacion", "cierre_postulacion"]
    assert inicial["documents_count"] == 0

    documento = TenderChatDocument(
        tender_id=dobles.tender.id,
        user_id=user_id,
        file_name="bases.pdf",
        file_type="pdf",
        file_size_bytes=10,
        storage_path="/tmp/bases.pdf",
    )
    dobles.chat.documents[documento.id] = (documento, b"%PDF")

    extraidos = await api.post(f"{ruta}/extract")

    assert extraidos.status_code == 200
    visita = next(m for m in extraidos.json()["milestones"] if m["kind"] == "visita_tecnica")
    assert visita["due_at"] == "2030-10-20T18:00:00Z"
    assert visita["source"] == "ia_documento"
    assert visita["urgency"] == "normal"


async def test_licitacion_inexistente(api: AsyncClient):
    await _login(api)

    respuesta = await api.get(f"/tenders/{uuid4()}/milestones")

    assert respuesta.status_code == 404
