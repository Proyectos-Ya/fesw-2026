import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
import respx
from httpx import Response

from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender, TenderItem
from app.domain.errors.document_analysis_quotation_errors import (
    DocumentAnalysisAndQuotationServiceError,
)
from app.infrastructure.services.gemini_document_analysis_and_quotation_service import (
    GeminiDocumentAnalysisAndQuotationService,
)


def create_test_tender() -> Tender:
    now = datetime.now(UTC).replace(tzinfo=None)
    return Tender(
        id=uuid4(),
        code="LIC-2026-001",
        name="Adquisición de Insumos Eléctricos",
        description="Licitación para suministro de cables y conectores",
        status_id=1,
        status_code="publicada",
        published_at=now,
        closing_at=now,
        last_change_at=now,
        buyer_rut="11.111.111-1",
        buyer_name="Hospital Regional",
        buyer_unit="Abastecimiento",
        items=[
            TenderItem(
                id=uuid4(),
                tender_id=uuid4(),
                name="Cable Cobre",
                product_code="CAB-01",
                quantity=10,
                unit_of_measure="rollo",
                description="Cable calibre 12",
            )
        ],
    )


def create_test_supplier() -> Supplier:
    return Supplier(
        id=uuid4(),
        rut="22.222.222-2",
        legal_name="Distribuidora Eléctrica Spa",
        trade_name="ElectroSur",
        description="Distribución de materiales e insumos eléctricos industriales",
        regions=["Metropolitana", "Valparaíso"],
        sectors=["Electricidad", "Construcción"],
        certifications=["ISO 9001"],
        keywords=["cable", "conector", "cobre"],
        years_experience=8,
        num_employees=25,
    )


@pytest.fixture
def service():
    return GeminiDocumentAnalysisAndQuotationService(
        api_key="test-api-key",
        model_name="gemini-2.5-flash",
    )


@pytest.mark.asyncio
@respx.mock
async def test_analyze_and_quote_pdf_success_exactly_one_call(service):
    tender = create_test_tender()
    supplier = create_test_supplier()
    pdf_bytes = b"%PDF-1.4 sample content for tender analysis"

    mock_gemini_payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "analysis": {
                                    "compatibility_score": 88.0,
                                    "recommendation": "Postular",
                                    "justification": "El proveedor cuenta con las certificaciones y experiencia requeridas.",
                                },
                                "quotation": {
                                    "currency": "CLP",
                                    "items": [
                                        {
                                            "description": "Cable Cobre 100m Calibre 12",
                                            "unit": "rollo",
                                            "quantity": 10,
                                            "unit_price": 45000,
                                            "subtotal": 450000,
                                        },
                                        {
                                            "description": "Conectores Industriales",
                                            "unit": "caja",
                                            "quantity": 2,
                                            "unit_price": 25000,
                                            "subtotal": 50000,
                                        },
                                    ],
                                    "total": 500000,
                                },
                            })
                        }
                    ]
                }
            }
        ]
    }

    gemini_route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=test-api-key"
    ).mock(return_value=Response(200, json=mock_gemini_payload))

    result = await service.analyze_and_quote(
        document_bytes=pdf_bytes,
        file_name="Bases_Tecnicas.pdf",
        file_type="pdf",
        tender=tender,
        supplier=supplier,
        matching_score=88.0,
    )

    # EXACTAMENTE 1 llamada HTTP a Gemini
    assert gemini_route.call_count == 1

    # Verificar estructura del request enviado
    sent_request = gemini_route.calls[0].request
    sent_data = json.loads(sent_request.content)
    assert "contents" in sent_data
    assert "generationConfig" in sent_data
    assert sent_data["generationConfig"]["responseMimeType"] == "application/json"
    schema = sent_data["generationConfig"]["responseSchema"]
    assert "analysis" in schema["properties"]
    assert "quotation" in schema["properties"]

    # Verificar partes enviadas (inlineData con base64 para PDF)
    parts = sent_data["contents"][0]["parts"]
    assert any("inlineData" in p and p["inlineData"]["mimeType"] == "application/pdf" for p in parts)

    # Verificar DeepAnalysis retornado
    assert result.analysis.tender_id == tender.id
    assert result.analysis.supplier_id == supplier.id
    assert result.analysis.compatibility_score == 88.0
    assert result.analysis.recommendation == "Postular"
    assert "certificaciones" in result.analysis.justification

    # Verificar QuotationInput retornado
    assert result.quotation.currency == "CLP"
    assert len(result.quotation.items) == 2
    assert result.quotation.items[0].description == "Cable Cobre 100m Calibre 12"
    assert result.quotation.items[0].quantity == Decimal("10")
    assert result.quotation.items[0].unit_price == Decimal("45000")
    assert result.quotation.items[0].subtotal == Decimal("450000.00")
    assert result.quotation.items[1].subtotal == Decimal("50000.00")
    assert result.quotation.total == Decimal("500000.00")


@pytest.mark.asyncio
@respx.mock
async def test_analyze_and_quote_enforces_matching_score_if_provided(service):
    tender = create_test_tender()
    supplier = create_test_supplier()

    mock_gemini_payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "analysis": {
                                    "compatibility_score": 99.0,  # Gemini devolvió 99.0
                                    "recommendation": "Postular",
                                    "justification": "Recomendación sólida.",
                                },
                                "quotation": {
                                    "currency": "CLP",
                                    "items": [
                                        {
                                            "description": "Item A",
                                            "unit": "UN",
                                            "quantity": 1,
                                            "unit_price": 1000,
                                            "subtotal": 1000,
                                        }
                                    ],
                                    "total": 1000,
                                },
                            })
                        }
                    ]
                }
            }
        ]
    }

    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=test-api-key"
    ).mock(return_value=Response(200, json=mock_gemini_payload))

    # Pasamos matching_score=75.5 explícito
    result = await service.analyze_and_quote(
        document_bytes=b"sample",
        file_name="doc.pdf",
        file_type="pdf",
        tender=tender,
        supplier=supplier,
        matching_score=75.5,
    )

    # Debe sobrescribir con el matching_score precalculado
    assert result.analysis.compatibility_score == 75.5


@pytest.mark.asyncio
@respx.mock
async def test_analyze_and_quote_uses_model_score_when_no_matching_score(service):
    tender = create_test_tender()
    supplier = create_test_supplier()

    mock_gemini_payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "analysis": {
                                    "compatibility_score": 65.0,
                                    "recommendation": "Evaluar con cautela",
                                    "justification": "Cumple parcialmente con la capacidad operativa.",
                                },
                                "quotation": {
                                    "currency": "CLP",
                                    "items": [
                                        {
                                            "description": "Servicio General",
                                            "unit": "GL",
                                            "quantity": 1,
                                            "unit_price": 500000,
                                            "subtotal": 500000,
                                        }
                                    ],
                                    "total": 500000,
                                },
                            })
                        }
                    ]
                }
            }
        ]
    }

    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=test-api-key"
    ).mock(return_value=Response(200, json=mock_gemini_payload))

    result = await service.analyze_and_quote(
        document_bytes=b"sample",
        file_name="doc.pdf",
        file_type="pdf",
        tender=tender,
        supplier=supplier,
        matching_score=None,
    )

    assert result.analysis.compatibility_score == 65.0
    assert result.analysis.recommendation == "Evaluar con cautela"


@pytest.mark.asyncio
@respx.mock
async def test_analyze_and_quote_handles_png_multimodal(service):
    tender = create_test_tender()
    supplier = create_test_supplier()

    mock_gemini_payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "analysis": {
                                    "compatibility_score": 80.0,
                                    "recommendation": "Postular",
                                    "justification": "El plano adjunto coincide con los servicios.",
                                },
                                "quotation": {
                                    "currency": "CLP",
                                    "items": [
                                        {
                                            "description": "Plano y Ejecución",
                                            "unit": "GL",
                                            "quantity": 1,
                                            "unit_price": 200000,
                                            "subtotal": 200000,
                                        }
                                    ],
                                    "total": 200000,
                                },
                            })
                        }
                    ]
                }
            }
        ]
    }

    route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=test-api-key"
    ).mock(return_value=Response(200, json=mock_gemini_payload))

    result = await service.analyze_and_quote(
        document_bytes=b"fake-png-bytes",
        file_name="plano.png",
        file_type="png",
        tender=tender,
        supplier=supplier,
    )

    assert route.call_count == 1
    sent_data = json.loads(route.calls[0].request.content)
    parts = sent_data["contents"][0]["parts"]
    assert any("inlineData" in p and p["inlineData"]["mimeType"] == "image/png" for p in parts)
    assert result.analysis.recommendation == "Postular"


@pytest.mark.asyncio
@respx.mock
async def test_analyze_and_quote_gemini_500_raises_service_error(service):
    tender = create_test_tender()
    supplier = create_test_supplier()

    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=test-api-key"
    ).mock(return_value=Response(500, text="Internal Server Error"))

    with pytest.raises(DocumentAnalysisAndQuotationServiceError, match="HTTP 500"):
        await service.analyze_and_quote(
            document_bytes=b"sample",
            file_name="doc.pdf",
            file_type="pdf",
            tender=tender,
            supplier=supplier,
        )


@pytest.mark.asyncio
@respx.mock
async def test_analyze_and_quote_invalid_json_raises_service_error(service):
    tender = create_test_tender()
    supplier = create_test_supplier()

    mock_gemini_payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": "Esto no es un JSON válido"
                        }
                    ]
                }
            }
        ]
    }

    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=test-api-key"
    ).mock(return_value=Response(200, json=mock_gemini_payload))

    with pytest.raises(DocumentAnalysisAndQuotationServiceError, match="No se pudo decodificar"):
        await service.analyze_and_quote(
            document_bytes=b"sample",
            file_name="doc.pdf",
            file_type="pdf",
            tender=tender,
            supplier=supplier,
        )
