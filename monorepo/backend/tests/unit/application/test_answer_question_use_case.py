from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.application.use_cases.questions.answer_question_use_case import (
    AnswerQuestionUseCase,
)
from app.domain.entities.question import Question
from app.domain.entities.supplier import Supplier
from tests.unit.application.fakes import (
    FakeEmbeddingService,
    FakeSupplierVectorRepository,
    InMemoryQuestionRepository,
    InMemorySupplierRepository,
)

VALID_RUT = "76086428-5"
SAMPLE_VECTOR = [0.1, 0.2, 0.3, 0.4]


@pytest.fixture
def supplier_repo() -> InMemorySupplierRepository:
    return InMemorySupplierRepository()


@pytest.fixture
def question_repo() -> InMemoryQuestionRepository:
    return InMemoryQuestionRepository()


@pytest.fixture
def vector_repo() -> FakeSupplierVectorRepository:
    return FakeSupplierVectorRepository()


@pytest.fixture
def embedding_service() -> FakeEmbeddingService:
    return FakeEmbeddingService(vector=SAMPLE_VECTOR)


@pytest.fixture
def use_case(
    supplier_repo: InMemorySupplierRepository,
    question_repo: InMemoryQuestionRepository,
    vector_repo: FakeSupplierVectorRepository,
    embedding_service: FakeEmbeddingService,
) -> AnswerQuestionUseCase:
    return AnswerQuestionUseCase(
        supplier_repo=supplier_repo,
        question_repo=question_repo,
        vector_repo=vector_repo,
        embedding_service=embedding_service,
    )


async def _seed_supplier(
    repo: InMemorySupplierRepository,
    user_id,
    keywords=None,
    negative_keywords=None,
) -> Supplier:
    supplier = Supplier(
        id=uuid4(),
        user_id=user_id,
        rut=VALID_RUT,
        legal_name="Empresa Test SpA",
        keywords=keywords or [],
        negative_keywords=negative_keywords or [],
    )
    return await repo.save(supplier)


async def _seed_question(
    repo: InMemoryQuestionRepository,
    provider_id,
    target_keyword="certificacion:iso_9001",
    tender_id=None,
) -> Question:
    question = Question(
        id=uuid4(),
        provider_id=provider_id,
        tender_id=tender_id or uuid4(),
        question="¿Cuenta con certificación ISO 9001?",
        target_profile_field="iso_certifications",
        target_keyword=target_keyword,
        options=["Sí", "No"],
    )
    return await repo.save(question)


@pytest.mark.asyncio
async def test_answer_question_updates_keywords_successfully_legacy(
    use_case: AnswerQuestionUseCase, supplier_repo: InMemorySupplierRepository
) -> None:
    """Verifica compatibilidad con llamadas anteriores que pasan field_name y answer."""
    user_id = uuid4()
    supplier = await _seed_supplier(supplier_repo, user_id)

    await use_case.execute(
        user_id=user_id,
        field_name="bim_capabilities",
        answer="Sí, nivel básico/intermedio",
    )

    updated_supplier = await supplier_repo.get_by_id(supplier.id)
    assert updated_supplier is not None
    keywords_actuales = updated_supplier.keywords or []
    assert "bim_capabilities:Sí, nivel básico/intermedio" in keywords_actuales


@pytest.mark.asyncio
async def test_answer_no_adds_negative_keyword_and_skips_vector_sync(
    use_case: AnswerQuestionUseCase,
    supplier_repo: InMemorySupplierRepository,
    question_repo: InMemoryQuestionRepository,
    vector_repo: FakeSupplierVectorRepository,
    embedding_service: FakeEmbeddingService,
) -> None:
    """Flujo 'No': marca answered=True, agrega negative_keywords con fecha, y NO toca Qdrant ni embeddings."""
    user_id = uuid4()
    supplier = await _seed_supplier(supplier_repo, user_id)
    question = await _seed_question(
        question_repo, supplier.id, target_keyword="certificacion:iso_9001"
    )

    embedding_spy = AsyncMock(wraps=embedding_service.embed)
    embedding_service.embed = embedding_spy

    await use_case.execute(
        user_id=user_id,
        question_id=question.id,
        answer="No",
    )

    # 1. Pregunta marcada respondida
    saved_q = await question_repo.get_by_id(question.id)
    assert saved_q is not None
    assert saved_q.answered is True
    assert saved_q.answer == "No"
    assert saved_q.answered_at is not None

    # 2. Supplier guardado con memoria negativa
    updated_supplier = await supplier_repo.get_by_id(supplier.id)
    assert updated_supplier is not None
    assert updated_supplier.negative_keywords is not None
    assert len(updated_supplier.negative_keywords) == 1
    neg = updated_supplier.negative_keywords[0]
    assert neg["keyword"] == "certificacion:iso_9001"
    assert "discarded_at" in neg

    # 3. NO debe estar en keywords
    assert "certificacion:iso_9001" not in (updated_supplier.keywords or [])

    # 4. Qdrant y embeddings NO llamados
    embedding_spy.assert_not_called()
    assert supplier.id not in vector_repo.vectors


@pytest.mark.asyncio
async def test_answer_si_adds_keyword_cleans_negative_and_syncs_qdrant(
    use_case: AnswerQuestionUseCase,
    supplier_repo: InMemorySupplierRepository,
    question_repo: InMemoryQuestionRepository,
    vector_repo: FakeSupplierVectorRepository,
) -> None:
    """Flujo 'Sí': marca answered, agrega a keywords, limpia negative_keywords, actualiza profile_changed_at y sincroniza Qdrant."""
    user_id = uuid4()
    initial_negatives = [
        {"keyword": "certificacion:iso_9001", "discarded_at": "2026-10-20T00:00:00"},
        {"keyword": "otra:restriccion", "discarded_at": "2026-10-20T00:00:00"},
    ]
    supplier = await _seed_supplier(
        supplier_repo, user_id, negative_keywords=initial_negatives
    )
    question = await _seed_question(
        question_repo, supplier.id, target_keyword="certificacion:iso_9001"
    )

    await use_case.execute(
        user_id=user_id,
        question_id=question.id,
        answer="Sí",
    )

    # 1. Pregunta actualizada
    saved_q = await question_repo.get_by_id(question.id)
    assert saved_q is not None
    assert saved_q.answered is True
    assert saved_q.answer == "Sí"

    # 2. Supplier con keyword y limpieza automática de negative_keywords
    updated_supplier = await supplier_repo.get_by_id(supplier.id)
    assert updated_supplier is not None
    assert "certificacion:iso_9001" in (updated_supplier.keywords or [])
    assert updated_supplier.negative_keywords == [
        {"keyword": "otra:restriccion", "discarded_at": "2026-10-20T00:00:00"}
    ]
    assert updated_supplier.profile_changed_at is not None

    # 3. Sincronizado en Qdrant
    assert supplier.id in vector_repo.vectors
    assert vector_repo.vectors[supplier.id] == SAMPLE_VECTOR


@pytest.mark.asyncio
async def test_answer_si_rolls_back_when_qdrant_fails(
    supplier_repo: InMemorySupplierRepository,
    question_repo: InMemoryQuestionRepository,
    vector_repo: FakeSupplierVectorRepository,
    embedding_service: FakeEmbeddingService,
) -> None:
    """Si Qdrant falla durante el flujo 'Sí', la transacción en Postgres se revierte."""
    user_id = uuid4()
    supplier = await _seed_supplier(supplier_repo, user_id)
    question = await _seed_question(
        question_repo, supplier.id, target_keyword="certificacion:iso_9001"
    )

    async def fail_upsert(*args, **kwargs):
        raise RuntimeError("Qdrant unavailable")

    vector_repo.upsert = fail_upsert

    rollback_spy = AsyncMock(wraps=supplier_repo.rollback)
    supplier_repo.rollback = rollback_spy

    use_case = AnswerQuestionUseCase(
        supplier_repo=supplier_repo,
        question_repo=question_repo,
        vector_repo=vector_repo,
        embedding_service=embedding_service,
    )

    with pytest.raises(RuntimeError, match="Qdrant unavailable"):
        await use_case.execute(
            user_id=user_id,
            question_id=question.id,
            answer="Sí",
        )

    rollback_spy.assert_awaited_once()


@pytest.mark.asyncio
async def test_answer_si_restores_vector_when_commit_fails(
    supplier_repo: InMemorySupplierRepository,
    question_repo: InMemoryQuestionRepository,
    vector_repo: FakeSupplierVectorRepository,
    embedding_service: FakeEmbeddingService,
) -> None:
    """Si el commit final de SQL falla, se restaura el vector previo en Qdrant."""
    user_id = uuid4()
    supplier = await _seed_supplier(supplier_repo, user_id)
    old_vector = [0.9, 0.9, 0.9, 0.9]
    vector_repo.vectors[supplier.id] = old_vector

    question = await _seed_question(
        question_repo, supplier.id, target_keyword="certificacion:iso_9001"
    )

    async def fail_commit():
        raise RuntimeError("SQL commit error")

    supplier_repo.commit = fail_commit

    use_case = AnswerQuestionUseCase(
        supplier_repo=supplier_repo,
        question_repo=question_repo,
        vector_repo=vector_repo,
        embedding_service=embedding_service,
    )

    with pytest.raises(RuntimeError, match="SQL commit error"):
        await use_case.execute(
            user_id=user_id,
            question_id=question.id,
            answer="Sí",
        )

    # El vector previo debe haber sido restaurado
    assert vector_repo.vectors[supplier.id] == old_vector


@pytest.mark.asyncio
async def test_answer_question_raises_when_question_not_found(
    use_case: AnswerQuestionUseCase,
    supplier_repo: InMemorySupplierRepository,
) -> None:
    """Si el question_id no existe, lanza ValueError."""
    user_id = uuid4()
    await _seed_supplier(supplier_repo, user_id)

    with pytest.raises(ValueError, match="no encontrada"):
        await use_case.execute(
            user_id=user_id,
            question_id=uuid4(),
            answer="Sí",
        )


@pytest.mark.asyncio
async def test_answer_question_raises_when_no_supplier(
    use_case: AnswerQuestionUseCase,
) -> None:
    """Si el usuario no tiene empresa, lanza ValueError."""
    with pytest.raises(ValueError, match="empresa"):
        await use_case.execute(
            user_id=uuid4(),
            question_id=uuid4(),
            answer="Sí",
        )
