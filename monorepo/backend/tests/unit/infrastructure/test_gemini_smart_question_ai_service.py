import json
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import respx
import httpx

from app.application.services.smart_question_ai_service import DynamicQuestionDTO
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender
from app.infrastructure.services.gemini_smart_question_ai_service import (
    GeminiSmartQuestionAIService,
    SmartQuestionAIUnavailable,
)

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"


@pytest.fixture
def service() -> GeminiSmartQuestionAIService:
    return GeminiSmartQuestionAIService(
        api_key="test-api-key",
        model_name="gemini-1.5-flash",
        retry_backoff_seconds=0,  # sin esperas en tests
    )


@pytest.fixture
def sample_tender() -> Tender:
    now = datetime(2026, 10, 27, 12, 0, 0)
    return Tender(
        id=uuid4(),
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


@pytest.fixture
def sample_supplier() -> Supplier:
    return Supplier(
        id=uuid4(),
        user_id=uuid4(),
        rut="76086428-5",
        legal_name="Constructora del Sur SpA",
        description="Obras menores y remodelaciones.",
        sectors=["construcción"],
        keywords=["obras_civiles"],
    )


def _gemini_response(questions: list[dict[str, object]]) -> dict[str, object]:
    content_str = json.dumps({"questions": questions})
    return {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": content_str}],
                    "role": "model",
                },
                "finishReason": "STOP",
            }
        ]
    }


def test_uses_gemini_1_5_flash_by_default() -> None:
    service = GeminiSmartQuestionAIService(api_key="key")
    assert service.model_name == "gemini-1.5-flash"


@respx.mock
async def test_sends_strict_json_schema_and_model_url(
    service: GeminiSmartQuestionAIService,
    sample_tender: Tender,
    sample_supplier: Supplier,
) -> None:
    """Verifica que apunte al endpoint de gemini-1.5-flash y configure responseSchema."""
    route = respx.post(BASE_URL).respond(200, json=_gemini_response([]))

    await service.generate_questions(
        tender=sample_tender,
        supplier=sample_supplier,
        attachment_texts=[],
        valid_negative_keywords=[],
    )

    assert route.called
    assert route.calls.last.request.headers.get("x-goog-api-key") == "test-api-key"
    payload = json.loads(route.calls.last.request.content)
    config = payload.get("generationConfig", {})
    assert config.get("responseMimeType") == "application/json"
    schema = config.get("responseSchema", {})
    assert schema.get("type") == "OBJECT"
    assert "questions" in schema.get("properties", {})


@respx.mock
async def test_prompt_injects_valid_negative_keywords(
    service: GeminiSmartQuestionAIService,
    sample_tender: Tender,
    sample_supplier: Supplier,
) -> None:
    """Verifica que las exclusiones activas se inyecten con directiva restrictiva en el prompt."""
    route = respx.post(BASE_URL).respond(200, json=_gemini_response([]))

    await service.generate_questions(
        tender=sample_tender,
        supplier=sample_supplier,
        attachment_texts=[],
        valid_negative_keywords=["certificacion:iso_9001", "maquinaria:grua_pluma"],
    )

    payload = json.loads(route.calls.last.request.content)
    prompt_text = payload["contents"][0]["parts"][0]["text"]

    assert "certificacion:iso_9001" in prompt_text
    assert "maquinaria:grua_pluma" in prompt_text
    assert "PROHIBIDO" in prompt_text or "NO" in prompt_text


@respx.mock
async def test_prompt_injects_attachment_texts_rag(
    service: GeminiSmartQuestionAIService,
    sample_tender: Tender,
    sample_supplier: Supplier,
) -> None:
    """Verifica que el texto de las bases técnicas/administrativas se incluya en el prompt."""
    route = respx.post(BASE_URL).respond(200, json=_gemini_response([]))

    rag_docs = [
        "Documento 'Bases.pdf': Se exige obligatoriamente Registro MOP en Primera Categoría.",
        "Documento 'Terminos.pdf': Boleta de garantía de seriedad por 200 UF.",
    ]

    await service.generate_questions(
        tender=sample_tender,
        supplier=sample_supplier,
        attachment_texts=rag_docs,
        valid_negative_keywords=[],
    )

    payload = json.loads(route.calls.last.request.content)
    prompt_text = payload["contents"][0]["parts"][0]["text"]

    assert "Registro MOP en Primera Categoría" in prompt_text
    assert "Boleta de garantía" in prompt_text


@respx.mock
async def test_parses_json_response_to_dtos(
    service: GeminiSmartQuestionAIService,
    sample_tender: Tender,
    sample_supplier: Supplier,
) -> None:
    """Verifica el parseo correcto de la respuesta JSON a instancias de DynamicQuestionDTO."""
    expected_data = [
        {
            "question": "¿Cuenta con registro vigente en el MOP en Primera Categoría?",
            "target_keyword": "registro:mop_primera",
            "options": ["Sí", "No"],
        },
        {
            "question": "¿Posee certificación en norma chilena NCh 2728?",
            "target_keyword": "certificacion:nch_2728",
            "options": ["Sí", "No"],
        },
    ]
    respx.post(BASE_URL).respond(200, json=_gemini_response(expected_data))

    dtos = await service.generate_questions(
        tender=sample_tender,
        supplier=sample_supplier,
        attachment_texts=[],
        valid_negative_keywords=[],
    )

    assert len(dtos) == 2
    assert isinstance(dtos[0], DynamicQuestionDTO)
    assert dtos[0].question == "¿Cuenta con registro vigente en el MOP en Primera Categoría?"
    assert dtos[0].target_keyword == "registro:mop_primera"
    assert dtos[0].options == ["Sí", "No"]
    assert dtos[1].target_keyword == "certificacion:nch_2728"


@respx.mock
async def test_retries_on_transient_error_and_succeeds(
    service: GeminiSmartQuestionAIService,
    sample_tender: Tender,
    sample_supplier: Supplier,
) -> None:
    """Verifica reintentos ante un error pasajero (HTTP 503)."""
    route = respx.post(BASE_URL)
    route.side_effect = [
        httpx.Response(503, json={"error": "service unavailable"}),
        httpx.Response(200, json=_gemini_response([{"question": "¿Q?", "target_keyword": "k:v"}])),
    ]

    dtos = await service.generate_questions(
        tender=sample_tender,
        supplier=sample_supplier,
        attachment_texts=[],
        valid_negative_keywords=[],
    )

    assert len(dtos) == 1
    assert route.call_count == 2


@respx.mock
async def test_raises_unavailable_on_persistent_failure(
    service: GeminiSmartQuestionAIService,
    sample_tender: Tender,
    sample_supplier: Supplier,
) -> None:
    """Si fallan todos los reintentos, lanza SmartQuestionAIUnavailable."""
    respx.post(BASE_URL).respond(500, json={"error": "internal error"})

    with pytest.raises(SmartQuestionAIUnavailable):
        await service.generate_questions(
            tender=sample_tender,
            supplier=sample_supplier,
            attachment_texts=[],
            valid_negative_keywords=[],
        )
