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
