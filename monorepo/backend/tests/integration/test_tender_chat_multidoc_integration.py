import io
import json
import pytest
import respx
import zipfile
from uuid import uuid4
from datetime import datetime, timezone
from fastapi import FastAPI, status
from httpx import AsyncClient, ASGITransport

from app.application.use_cases.upload_tender_chat_document_use_case import UploadTenderChatDocumentUseCase
from app.application.use_cases.list_tender_chat_documents_use_case import ListTenderChatDocumentsUseCase
from app.application.use_cases.delete_tender_chat_document_use_case import DeleteTenderChatDocumentUseCase
from app.application.use_cases.ask_tender_assistant_use_case import AskTenderAssistantUseCase
from app.application.use_cases.get_tender_chat_history_use_case import GetTenderChatHistoryUseCase
from app.application.use_cases.create_tender_chat_session_use_case import CreateTenderChatSessionUseCase
from app.domain.entities.user import User
from app.infrastructure.routers.tender_chat import create_tender_chat_router
from app.infrastructure.services.gemini_tender_assistant_service import GeminiTenderAssistantService
from app.infrastructure.services.document_validator_service import DocumentValidatorService
from tests.unit.application.fakes import InMemoryTenderChatRepository


def _create_minimal_pdf(title: str = "Bases") -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n0000000102 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n180\n%%EOF"
    )


def _create_minimal_xlsx() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types></Types>')
        zf.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook></workbook>')
    return buf.getvalue()


@pytest.fixture
def current_user():
    return User(
        id=uuid4(),
        email="representante@constructora.cl",
        hashed_password="hashed_pass",
        full_name="Constanza Pérez",
        active=True,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )


@pytest.fixture
def app_with_services(current_user):
    app = FastAPI()
    repo = InMemoryTenderChatRepository()
    validator_service = DocumentValidatorService()
    ai_service = GeminiTenderAssistantService(api_key="integration-test-key", model_name="gemini-3.1-flash-lite")

    upload_use_case = UploadTenderChatDocumentUseCase(chat_repo=repo, validator_service=validator_service)
    list_use_case = ListTenderChatDocumentsUseCase(chat_repo=repo)
    delete_use_case = DeleteTenderChatDocumentUseCase(chat_repo=repo)
    ask_use_case = AskTenderAssistantUseCase(
        chat_repo=repo,
        ai_service=ai_service,
        supplier_repo=None,
        validator_service=validator_service,
    )
    get_history_use_case = GetTenderChatHistoryUseCase(chat_repo=repo)
    create_session_use_case = CreateTenderChatSessionUseCase(chat_repo=repo)

    router = create_tender_chat_router(
        get_current_user=lambda: current_user,
        get_upload_doc_use_case=lambda: upload_use_case,
        get_list_docs_use_case=lambda: list_use_case,
        get_delete_doc_use_case=lambda: delete_use_case,
        get_ask_assistant_use_case=lambda: ask_use_case,
        get_chat_history_use_case=lambda: get_history_use_case,
        get_create_chat_session_use_case=lambda: create_session_use_case,
    )
    app.include_router(router)
    return app, repo


@pytest.mark.asyncio
@respx.mock
async def test_ca1_and_ca2_cross_referencing_and_discrepancies(app_with_services):
    """CA1 & CA2: Cruce de múltiples documentos y detección de discrepancias con fuentes contradictorias."""
    app, repo = app_with_services
    tender_id = uuid4()

    # Subir 2 documentos válidos
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Doc 1: Bases Administrativas
        pdf1 = _create_minimal_pdf("Bases Administrativas")
        await client.post(
            f"/tenders/{tender_id}/assistant/documents",
            files={"file": ("Bases_Administrativas.pdf", pdf1, "application/pdf")}
        )
        # Doc 2: Especificaciones Técnicas
        pdf2 = _create_minimal_pdf("Especificaciones Técnicas")
        await client.post(
            f"/tenders/{tender_id}/assistant/documents",
            files={"file": ("Especificaciones_Tecnicas.pdf", pdf2, "application/pdf")}
        )

        # Mock respuesta de Gemini cruzando ambos documentos y reportando discrepancia
        mock_gemini_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps({
                                    "answer": "Se encontraron los requisitos de instalación, pero existe una contradicción en el plazo de entrega.",
                                    "citations": [
                                        {
                                            "document_name": "Bases_Administrativas.pdf",
                                            "page_or_sheet": "Página 5",
                                            "quote": "Plazo de entrega: 30 días corridos"
                                        },
                                        {
                                            "document_name": "Especificaciones_Tecnicas.pdf",
                                            "page_or_sheet": "Página 12",
                                            "quote": "Plazo de ejecución técnica: 45 días corridos"
                                        }
                                    ],
                                    "discrepancies": [
                                        {
                                            "topic": "Plazo de entrega y ejecución",
                                            "description": "Las bases administrativas estipulan 30 días mientras que las especificaciones técnicas indican 45 días.",
                                            "conflicting_sources": [
                                                {
                                                    "document_name": "Bases_Administrativas.pdf",
                                                    "page_or_sheet": "Página 5",
                                                    "quote": "Plazo de entrega: 30 días corridos"
                                                },
                                                {
                                                    "document_name": "Especificaciones_Tecnicas.pdf",
                                                    "page_or_sheet": "Página 12",
                                                    "quote": "Plazo de ejecución técnica: 45 días corridos"
                                                }
                                            ]
                                        }
                                    ],
                                    "unbacked_aspects": [],
                                    "has_sufficient_info": True
                                })
                            }
                        ]
                    }
                }
            ]
        }

        respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key=integration-test-key"
        ).respond(status_code=200, json=mock_gemini_response)

        # Consultar al asistente
        ask_resp = await client.post(
            f"/tenders/{tender_id}/assistant/ask",
            json={"question": "¿Cuál es el plazo de entrega y los requisitos técnicos?"}
        )

        assert ask_resp.status_code == status.HTTP_200_OK
        data = ask_resp.json()
        assert len(data["citations"]) == 2
        assert len(data["discrepancies"]) == 1
        assert data["discrepancies"][0]["topic"] == "Plazo de entrega y ejecución"
        assert len(data["discrepancies"][0]["conflicting_sources"]) == 2


@pytest.mark.asyncio
@respx.mock
async def test_ca3_and_ca4_partial_backing_and_anti_hallucination(app_with_services):
    """CA3 & CA4: Respuesta con respaldo parcial y advertencia anti-alucinación de requisitos no existentes."""
    app, repo = app_with_services
    tender_id = uuid4()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Subir 1 documento
        xlsx_bytes = _create_minimal_xlsx()
        await client.post(
            f"/tenders/{tender_id}/assistant/documents",
            files={"file": ("Anexo_Economico.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )

        mock_gemini_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps({
                                    "answer": "Se encontró el formato de oferta económica en la planilla adjunta, pero el presupuesto máximo disponible no está especificado en los documentos.",
                                    "citations": [
                                        {
                                            "document_name": "Anexo_Economico.xlsx",
                                            "page_or_sheet": "Hoja 1",
                                            "quote": "Cuadro de precios unitarios netos"
                                        }
                                    ],
                                    "discrepancies": [],
                                    "unbacked_aspects": ["Presupuesto máximo disponible"],
                                    "has_sufficient_info": False
                                })
                            }
                        ]
                    }
                }
            ]
        }

        respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key=integration-test-key"
        ).respond(status_code=200, json=mock_gemini_response)

        ask_resp = await client.post(
            f"/tenders/{tender_id}/assistant/ask",
            json={"question": "¿Cómo se cotiza y cuál es el presupuesto máximo de la licitación?"}
        )

        assert ask_resp.status_code == status.HTTP_200_OK
        data = ask_resp.json()
        assert len(data["citations"]) == 1
        assert data["unbacked_aspects"] == ["Presupuesto máximo disponible"]
        assert data["has_sufficient_info"] is False


@pytest.mark.asyncio
async def test_ca5_limit_of_10_documents(app_with_services):
    """CA5: Se pueden subir hasta 10 documentos por licitación y el 11vo es rechazado con 400."""
    app, repo = app_with_services
    tender_id = uuid4()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        pdf_bytes = _create_minimal_pdf()
        for i in range(10):
            resp = await client.post(
                f"/tenders/{tender_id}/assistant/documents",
                files={"file": (f"documento_{i+1}.pdf", pdf_bytes, "application/pdf")}
            )
            assert resp.status_code == status.HTTP_201_CREATED

        # Intento de subir el documento número 11
        resp_11 = await client.post(
            f"/tenders/{tender_id}/assistant/documents",
            files={"file": ("documento_11.pdf", pdf_bytes, "application/pdf")}
        )
        assert resp_11.status_code == status.HTTP_400_BAD_REQUEST
        assert "10 documentos" in resp_11.json()["detail"]


@pytest.mark.asyncio
@respx.mock
async def test_ca6_corrupted_document_rejection_and_graceful_isolation(app_with_services, current_user):
    """CA6: Registro de documento corrupto al subir y aislamiento con advertencia en consulta cuando se requiere ese documento."""
    app, repo = app_with_services
    tender_id = uuid4()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Subir archivo corrupto (se registra para que la IA sepa que existe pero está dañado)
        corrupt_bytes = b"Esto no es un archivo PDF ni XLSX ni PNG valido."
        resp_bad_upload = await client.post(
            f"/tenders/{tender_id}/assistant/documents",
            files={"file": ("archivo_corrupto.pdf", corrupt_bytes, "application/pdf")}
        )
        assert resp_bad_upload.status_code == status.HTTP_201_CREATED

        # 2. Subir un archivo sano
        pdf_sano = _create_minimal_pdf("Documento Sano")
        resp_ok = await client.post(
            f"/tenders/{tender_id}/assistant/documents",
            files={"file": ("bases_sanas.pdf", pdf_sano, "application/pdf")}
        )
        assert resp_ok.status_code == status.HTTP_201_CREATED

        # Configurar mock de Gemini para la consulta
        mock_gemini_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps({
                                    "answer": "Información obtenida de las bases sanas. El archivo 'archivo_corrupto.pdf' se encuentra dañado y no fue posible procesarlo.",
                                    "citations": [
                                        {
                                            "document_name": "bases_sanas.pdf",
                                            "page_or_sheet": "Página 1",
                                            "quote": "Requisitos generales"
                                        }
                                    ],
                                    "discrepancies": [],
                                    "unbacked_aspects": [],
                                    "has_sufficient_info": True
                                })
                            }
                        ]
                    }
                }
            ]
        }
        respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key=integration-test-key"
        ).respond(status_code=200, json=mock_gemini_response)

        # 3. Realizar consulta: debe responder con éxito y listar el warning del archivo corrupto
        resp_query = await client.post(
            f"/tenders/{tender_id}/assistant/ask",
            json={"question": "¿Cuáles son los requisitos de las bases y del archivo corrupto?"}
        )
        assert resp_query.status_code == status.HTTP_200_OK
        data = resp_query.json()
        assert len(data["warnings"]) >= 1
        assert any("archivo_corrupto.pdf" in w for w in data["warnings"])
        assert any("dañado o su texto es ilegible" in w for w in data["warnings"])
