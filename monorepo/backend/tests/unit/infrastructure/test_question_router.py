from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domain.entities.question import Question
from app.infrastructure.routers.question import create_question_router


def _make_question(**kwargs) -> Question:
    defaults = {
        "id": uuid4(),
        "provider_id": uuid4(),
        "question": "¿Pregunta de prueba?",
        "target_profile_field": "test_field",
        "target_category": "general",
        "options": ["Sí", "No"],
        "tender_id": uuid4(),
        "target_keyword": "certificacion:iso_9001",
    }
    defaults.update(kwargs)
    return Question(**defaults)


@pytest.fixture
def current_user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), email="test@empresa.cl")


@pytest.fixture
def mock_smart_question_use_case() -> AsyncMock:
    uc = AsyncMock()
    uc.execute.return_value = [_make_question(question="Pregunta Legacy")]
    return uc


@pytest.fixture
def mock_answer_question_use_case() -> AsyncMock:
    uc = AsyncMock()
    uc.execute.return_value = None
    return uc


@pytest.fixture
def mock_generate_tender_use_case() -> AsyncMock:
    uc = AsyncMock()
    uc.execute.return_value = [
        _make_question(question="Pregunta Dinámica IA", target_keyword="certificacion:iso_9001")
    ]
    return uc


@pytest.fixture
def client(
    current_user: SimpleNamespace,
    mock_smart_question_use_case: AsyncMock,
    mock_answer_question_use_case: AsyncMock,
    mock_generate_tender_use_case: AsyncMock,
) -> TestClient:
    app = FastAPI()
    router = create_question_router(
        get_smart_question_use_case=lambda: mock_smart_question_use_case,
        get_answer_question_use_case=lambda: mock_answer_question_use_case,
        get_current_user=lambda: current_user,
        get_generate_tender_smart_questions_use_case=lambda: mock_generate_tender_use_case,
    )
    app.include_router(router)
    return TestClient(app)


def test_get_questions_without_tender_id_calls_legacy_use_case(
    client: TestClient,
    current_user: SimpleNamespace,
    mock_smart_question_use_case: AsyncMock,
    mock_generate_tender_use_case: AsyncMock,
) -> None:
    """GET /questions sin tender_id ejecuta el caso de uso legacy de preguntas del perfil."""
    response = client.get("/questions")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["question"] == "Pregunta Legacy"
    mock_smart_question_use_case.execute.assert_awaited_once_with(user_id=current_user.id)
    mock_generate_tender_use_case.execute.assert_not_called()


def test_get_questions_with_tender_id_calls_dynamic_use_case(
    client: TestClient,
    current_user: SimpleNamespace,
    mock_smart_question_use_case: AsyncMock,
    mock_generate_tender_use_case: AsyncMock,
) -> None:
    """GET /questions?tender_id={id} ejecuta GenerateTenderSmartQuestionsUseCase."""
    tender_id = uuid4()
    response = client.get(f"/questions?tender_id={tender_id}")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["question"] == "Pregunta Dinámica IA"
    assert data[0]["target_keyword"] == "certificacion:iso_9001"
    mock_generate_tender_use_case.execute.assert_awaited_once_with(
        user_id=current_user.id, tender_id=tender_id
    )
    mock_smart_question_use_case.execute.assert_not_called()


def test_get_questions_with_tender_id_handles_value_error_as_400(
    client: TestClient,
    current_user: SimpleNamespace,
    mock_generate_tender_use_case: AsyncMock,
) -> None:
    """Si GenerateTenderSmartQuestionsUseCase lanza ValueError, retorna 400 Bad Request."""
    mock_generate_tender_use_case.execute.side_effect = ValueError("Licitación no encontrada.")
    response = client.get(f"/questions?tender_id={uuid4()}")

    assert response.status_code == 400
    assert response.json()["detail"] == "Licitación no encontrada."


def test_post_answer_with_clean_payload(
    client: TestClient,
    current_user: SimpleNamespace,
    mock_answer_question_use_case: AsyncMock,
) -> None:
    """POST /questions/answer acepta { question_id, answer: 'Sí' } e invoca el caso de uso."""
    q_id = uuid4()
    response = client.post(
        "/questions/answer",
        json={"question_id": str(q_id), "answer": "Sí"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_answer_question_use_case.execute.assert_awaited_once_with(
        user_id=current_user.id,
        question_id=q_id,
        answer="Sí",
        field_name=None,
    )


def test_post_answer_handles_no_answer(
    client: TestClient,
    current_user: SimpleNamespace,
    mock_answer_question_use_case: AsyncMock,
) -> None:
    """POST /questions/answer acepta respuesta 'No' para memoria negativa."""
    q_id = uuid4()
    response = client.post(
        "/questions/answer",
        json={"question_id": str(q_id), "answer": "No"},
    )

    assert response.status_code == 200
    mock_answer_question_use_case.execute.assert_awaited_once_with(
        user_id=current_user.id,
        question_id=q_id,
        answer="No",
        field_name=None,
    )


def test_post_answer_handles_value_error_as_400(
    client: TestClient,
    mock_answer_question_use_case: AsyncMock,
) -> None:
    """POST /questions/answer maneja errores de validación como 400."""
    mock_answer_question_use_case.execute.side_effect = ValueError("Pregunta no encontrada.")
    response = client.post(
        "/questions/answer",
        json={"question_id": str(uuid4()), "answer": "Sí"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Pregunta no encontrada."
