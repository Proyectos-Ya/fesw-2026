import json
import pytest
import respx
import httpx
from uuid import uuid4
from io import BytesIO

from app.application.services.tender_assistant_ai_service import DocumentContextDTO
from app.domain.entities.tender_chat import TenderChatMessage
from app.domain.errors.tender_chat_errors import TenderAssistantUnavailableError
from app.infrastructure.services.gemini_tender_assistant_service import GeminiTenderAssistantService


@pytest.fixture
def service():
    return GeminiTenderAssistantService(api_key="test-api-key", model_name="gemini-3.1-flash-lite")


@pytest.mark.asyncio
@respx.mock
async def test_generate_response_success_with_pdf(service):
    # Mock de respuesta de Gemini API
    mock_gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "answer": "El plazo de entrega es de 3 días según las bases.",
                                "citations": [
                                    {
                                        "document_name": "terminos_catemu.pdf",
                                        "page_or_sheet": "Página 2",
                                        "quote": "plazo de entrega: 3 días corridos"
                                    }
                                ],
                                "has_sufficient_info": True
                            })
                        }
                    ]
                }
            }
        ]
    }

    route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key=test-api-key"
    ).respond(status_code=200, json=mock_gemini_response)

    pdf_doc = DocumentContextDTO(
        document_name="terminos_catemu.pdf",
        file_type="pdf",
        file_bytes=b"%PDF-1.4 sample content"
    )

    response = await service.generate_response(
        question="¿Cuál es el plazo de entrega?",
        history=[],
        documents=[pdf_doc]
    )

    assert route.called
    assert response.answer == "El plazo de entrega es de 3 días según las bases."
    assert len(response.citations) == 1
    assert response.citations[0].document_name == "terminos_catemu.pdf"
    assert response.citations[0].quote == "plazo de entrega: 3 días corridos"
    assert response.has_sufficient_info is True


@pytest.mark.asyncio
@respx.mock
async def test_generate_response_insufficient_info(service):
    mock_gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "answer": "Los documentos de esta licitación no contienen información suficiente sobre el tipo de garantía solicitada.",
                                "citations": [],
                                "has_sufficient_info": False
                            })
                        }
                    ]
                }
            }
        ]
    }

    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key=test-api-key"
    ).respond(status_code=200, json=mock_gemini_response)

    response = await service.generate_response(
        question="¿Qué tipo de boleta de garantía piden?",
        history=[],
        documents=[]
    )

    assert response.has_sufficient_info is False
    assert "no contienen información suficiente" in response.answer
    assert response.citations == []


@pytest.mark.asyncio
@respx.mock
async def test_gemini_api_500_raises_unavailable_error(service):
    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key=test-api-key"
    ).respond(status_code=500, text="Internal Server Error")

    with pytest.raises(TenderAssistantUnavailableError, match="El asistente virtual se encuentra temporalmente fuera de servicio"):
        await service.generate_response(
            question="¿Cuál es el presupuesto?",
            history=[],
            documents=[]
        )


@pytest.mark.asyncio
@respx.mock
async def test_gemini_network_timeout_raises_unavailable_error(service):
    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key=test-api-key"
    ).mock(side_effect=httpx.ConnectTimeout("Connection timed out"))

    with pytest.raises(TenderAssistantUnavailableError, match="El asistente virtual se encuentra temporalmente fuera de servicio"):
        await service.generate_response(
            question="¿Cuál es el presupuesto?",
            history=[],
            documents=[]
        )


@pytest.mark.asyncio
@respx.mock
async def test_generate_response_includes_multi_turn_history(service):
    mock_gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "answer": "La vigencia de la boleta de garantía debe ser de 90 días corridos.",
                                "citations": [
                                    {
                                        "document_name": "bases.pdf",
                                        "page_or_sheet": "Página 4",
                                        "quote": "vigencia mínima de 90 días"
                                    }
                                ],
                                "has_sufficient_info": True
                            })
                        }
                    ]
                }
            }
        ]
    }

    route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key=test-api-key"
    ).respond(status_code=200, json=mock_gemini_response)

    tender_id = uuid4()
    user_id = uuid4()
    history = [
        TenderChatMessage(
            tender_id=tender_id,
            user_id=user_id,
            role="user",
            content="¿Exigen boleta de garantía?",
        ),
        TenderChatMessage(
            tender_id=tender_id,
            user_id=user_id,
            role="assistant",
            content="Sí, se exige boleta de seriedad de la oferta.",
        ),
    ]

    response = await service.generate_response(
        question="¿Y qué vigencia debe tener?",
        history=history,
        documents=[]
    )

    assert route.called
    sent_payload = json.loads(route.calls.last.request.content.decode("utf-8"))
    contents = sent_payload["contents"]
    assert len(contents) == 3
    assert contents[0]["role"] == "user"
    assert contents[0]["parts"][0]["text"] == "¿Exigen boleta de garantía?"
    assert contents[1]["role"] == "model"
    assert contents[1]["parts"][0]["text"] == "Sí, se exige boleta de seriedad de la oferta."
    assert contents[2]["role"] == "user"
    assert any("Pregunta del usuario: ¿Y qué vigencia debe tener?" in p.get("text", "") for p in contents[2]["parts"])

    assert response.has_sufficient_info is True
    assert "90 días corridos" in response.answer


@pytest.mark.asyncio
@respx.mock
async def test_generate_response_applies_sliding_window_limit():
    service = GeminiTenderAssistantService(api_key="test-api-key", max_history_turns=2)
    mock_gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "answer": "Respuesta al turno final.",
                                "citations": [],
                                "has_sufficient_info": True
                            })
                        }
                    ]
                }
            }
        ]
    }

    route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key=test-api-key"
    ).respond(status_code=200, json=mock_gemini_response)

    tender_id = uuid4()
    user_id = uuid4()
    # Generar 6 turnos de historial
    history = [
        TenderChatMessage(tender_id=tender_id, user_id=user_id, role="user", content=f"Pregunta {i}")
        if i % 2 == 0
        else TenderChatMessage(tender_id=tender_id, user_id=user_id, role="assistant", content=f"Respuesta {i}")
        for i in range(6)
    ]

    await service.generate_response(
        question="Pregunta actual",
        history=history,
        documents=[]
    )

    assert route.called
    sent_payload = json.loads(route.calls.last.request.content.decode("utf-8"))
    contents = sent_payload["contents"]
    # 2 turnos de historial recortado + 1 turno actual = 3 turnos
    assert len(contents) == 3
    assert contents[0]["parts"][0]["text"] == "Pregunta 4"
    assert contents[1]["parts"][0]["text"] == "Respuesta 5"

