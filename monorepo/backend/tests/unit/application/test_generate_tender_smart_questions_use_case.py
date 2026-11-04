from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.application.services.anexos_visibles import AnexoVisible
from app.application.services.smart_question_ai_service import DynamicQuestionDTO
from app.application.use_cases.questions.generate_tender_smart_questions_use_case import (
    GenerateTenderSmartQuestionsUseCase,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
)
from app.domain.entities.question import Question
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender
from tests.unit.application.fakes import (
    FakeSmartQuestionAIService,
    InMemoryQuestionRepository,
    InMemorySupplierRepository,
    InMemoryTenderRepository,
)

VALID_RUT = "76086428-5"


@pytest.fixture
def question_repo() -> InMemoryQuestionRepository:
    return InMemoryQuestionRepository()


@pytest.fixture
def supplier_repo() -> InMemorySupplierRepository:
    return InMemorySupplierRepository()


@pytest.fixture
def tender_repo() -> InMemoryTenderRepository:
    return InMemoryTenderRepository()


@pytest.fixture
def ai_service() -> FakeSmartQuestionAIService:
    return FakeSmartQuestionAIService(
        questions=[
            DynamicQuestionDTO(
                question="¿Cuenta con certificación ISO 9001?",
                target_keyword="certificacion:iso_9001",
                options=["Sí", "No"],
            ),
            DynamicQuestionDTO(
                question="¿Dispone de flota de camiones tolva propia?",
                target_keyword="maquinaria:camion_tolva",
                options=["Sí", "No"],
            ),
        ]
    )


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 10, 27, 12, 0, 0)


@pytest.fixture
def use_case(
    question_repo: InMemoryQuestionRepository,
    supplier_repo: InMemorySupplierRepository,
    tender_repo: InMemoryTenderRepository,
    ai_service: FakeSmartQuestionAIService,
    fixed_now: datetime,
) -> GenerateTenderSmartQuestionsUseCase:
    return GenerateTenderSmartQuestionsUseCase(
        question_repo=question_repo,
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        ai_service=ai_service,
        now_func=lambda: fixed_now,
    )


async def _seed_supplier(repo: InMemorySupplierRepository, user_id, negative_keywords=None) -> Supplier:
    supplier = Supplier(
        id=uuid4(),
        user_id=user_id,
        rut=VALID_RUT,
        legal_name="Constructora SpA",
        negative_keywords=negative_keywords or [],
    )
    return await repo.save(supplier)


def _seed_tender(repo: InMemoryTenderRepository, tender_id: UUID | None = None) -> Tender:
    now = datetime(2026, 10, 27, 12, 0, 0)
    tender = Tender(
        id=tender_id or uuid4(),
        code="1234-56-LP26",
        name="Construcción Escuela Básica",
        description="Obras civiles para escuela básica.",
        status_id=1,
        status_code="publicada",
        published_at=now - timedelta(days=1),
        closing_at=now + timedelta(days=10),
        last_change_at=now,
        buyer_rut="12.345.678-9",
        buyer_name="Municipalidad",
        buyer_unit="Obras",
        items=[],
    )
    repo.tenders[tender.id] = tender
    return tender


@pytest.mark.asyncio
async def test_idempotency_returns_existing_questions_without_ai_call(
    use_case: GenerateTenderSmartQuestionsUseCase,
    question_repo: InMemoryQuestionRepository,
    supplier_repo: InMemorySupplierRepository,
    tender_repo: InMemoryTenderRepository,
    ai_service: FakeSmartQuestionAIService,
) -> None:
    """Idempotencia: Si ya existen preguntas para (provider_id, tender_id), las devuelve sin llamar a la IA."""
    user_id = uuid4()
    supplier = await _seed_supplier(supplier_repo, user_id)
    tender = _seed_tender(tender_repo)

    existing_q = Question(
        provider_id=supplier.id,
        tender_id=tender.id,
        question="¿Pregunta existente precalculada?",
        target_profile_field="field",
        target_keyword="custom:keyword",
    )
    await question_repo.save(existing_q)

    ai_spy = AsyncMock(wraps=ai_service.generate_questions)
    ai_service.generate_questions = ai_spy

    result = await use_case.execute(user_id=user_id, tender_id=tender.id)

    assert len(result) == 1
    assert result[0].id == existing_q.id
    assert result[0].question == "¿Pregunta existente precalculada?"
    ai_spy.assert_not_called()


@pytest.mark.asyncio
async def test_negative_memory_ttl_filters_older_than_6_months(
    use_case: GenerateTenderSmartQuestionsUseCase,
    supplier_repo: InMemorySupplierRepository,
    tender_repo: InMemoryTenderRepository,
    ai_service: FakeSmartQuestionAIService,
    fixed_now: datetime,
) -> None:
    """Filtro TTL 6 meses: Solo envía a la IA exclusiones con discarded_at menor a 6 meses (180 días)."""
    user_id = uuid4()
    recent_date = (fixed_now - timedelta(days=30)).isoformat()
    expired_date = (fixed_now - timedelta(days=210)).isoformat()

    negative_keywords = [
        {"keyword": "certificacion:iso_9001", "discarded_at": recent_date},
        {"keyword": "maquinaria:antigua", "discarded_at": expired_date},
    ]
    supplier = await _seed_supplier(supplier_repo, user_id, negative_keywords=negative_keywords)
    tender = _seed_tender(tender_repo)

    await use_case.execute(user_id=user_id, tender_id=tender.id)

    assert ai_service.last_valid_negative_keywords == ["certificacion:iso_9001"]
    assert "maquinaria:antigua" not in ai_service.last_valid_negative_keywords


@pytest.mark.asyncio
async def test_generates_and_persists_new_questions_associated_with_tender(
    use_case: GenerateTenderSmartQuestionsUseCase,
    question_repo: InMemoryQuestionRepository,
    supplier_repo: InMemorySupplierRepository,
    tender_repo: InMemoryTenderRepository,
) -> None:
    """Generación normal: Llama a la IA, persiste las preguntas con tender_id y las retorna."""
    user_id = uuid4()
    supplier = await _seed_supplier(supplier_repo, user_id)
    tender = _seed_tender(tender_repo)

    result = await use_case.execute(user_id=user_id, tender_id=tender.id)

    assert len(result) == 2
    assert result[0].tender_id == tender.id
    assert result[0].provider_id == supplier.id
    assert result[0].target_keyword == "certificacion:iso_9001"
    assert result[0].options == ["Sí", "No"]
    assert result[0].answered is False

    # Verificar persistencia en el repositorio
    saved_in_repo = await question_repo.get_by_provider_and_tender(supplier.id, tender.id)
    assert len(saved_in_repo) == 2


@pytest.mark.asyncio
async def test_rag_context_extracts_pdf_text_from_visible_attachments(
    question_repo: InMemoryQuestionRepository,
    supplier_repo: InMemorySupplierRepository,
    tender_repo: InMemoryTenderRepository,
    ai_service: FakeSmartQuestionAIService,
    fixed_now: datetime,
) -> None:
    """Contexto RAG: Obtiene anexos visibles y extrae texto de PDFs para inyectarlo al servicio IA."""
    user_id = uuid4()
    supplier = await _seed_supplier(supplier_repo, user_id)
    tender = _seed_tender(tender_repo)

    files_repo = AsyncMock()
    attachments_repo = AsyncMock()
    storage = AsyncMock()

    # Simulamos un anexo PDF visible
    archivo = AttachmentFile(
        id=uuid4(),
        tender_attachment_id=uuid4(),
        tender_id=tender.id,
        storage_key="attachments/bases.pdf",
        status=AttachmentFileStatus.STORED,
        sha256="fake-sha256",
        size_bytes=1024,
        source=AttachmentFileSource.MANUAL,
        uploader_user_id=user_id,
        workspace_id=supplier.id,
        created_at=datetime(2026, 10, 27, 10, 0, 0),
    )
    files_repo.list_visible_for_tender.return_value = [archivo]

    anexo_info = MagicMock()
    anexo_info.name = "Bases_Tecnicas.pdf"
    anexo_info.ext = "pdf"
    attachments_repo.get_attachment.return_value = anexo_info

    storage.get_bytes.return_value = b"%PDF-1.4 dummy"

    use_case = GenerateTenderSmartQuestionsUseCase(
        question_repo=question_repo,
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        ai_service=ai_service,
        files_repo=files_repo,
        attachments_repo=attachments_repo,
        storage=storage,
        now_func=lambda: fixed_now,
    )

    # Mockeamos pdf_paginas para aislar el parser de PDF en este test unitario
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.application.use_cases.questions.generate_tender_smart_questions_use_case.pdf_paginas",
            lambda datos: ["Exigencia: Certificación ISO 9001 obligatoria."],
        )
        await use_case.execute(user_id=user_id, tender_id=tender.id)

    assert len(ai_service.last_attachment_texts) == 1
    assert "Bases_Tecnicas.pdf" in ai_service.last_attachment_texts[0]
    assert "Certificación ISO 9001 obligatoria" in ai_service.last_attachment_texts[0]


@pytest.mark.asyncio
async def test_raises_when_supplier_not_found(
    use_case: GenerateTenderSmartQuestionsUseCase,
    tender_repo: InMemoryTenderRepository,
) -> None:
    """Si el usuario no tiene empresa asociada, lanza ValueError."""
    tender = _seed_tender(tender_repo)
    with pytest.raises(ValueError, match="empresa"):
        await use_case.execute(user_id=uuid4(), tender_id=tender.id)


@pytest.mark.asyncio
async def test_raises_when_tender_not_found(
    use_case: GenerateTenderSmartQuestionsUseCase,
    supplier_repo: InMemorySupplierRepository,
) -> None:
    """Si la licitación no existe, lanza ValueError."""
    user_id = uuid4()
    await _seed_supplier(supplier_repo, user_id)
    with pytest.raises(ValueError, match="Licitación no encontrada"):
        await use_case.execute(user_id=user_id, tender_id=uuid4())
