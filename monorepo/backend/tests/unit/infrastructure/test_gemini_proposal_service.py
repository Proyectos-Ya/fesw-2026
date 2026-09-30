"""Servicio de Gemini para la factibilidad de una postulación (HU-20, B2).

Se simula la API de Gemini: lo que importa es qué se le manda (ficha, catálogo
con sus ids, claves del banco, adjuntos) y cómo se interpreta lo que devuelve.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from app.application.services.proposal_ai_service import ProposalAIServiceError
from app.application.services.tender_assistant_ai_service import DocumentContextDTO
from app.domain.entities.capability import (
    CapabilityOption,
    CapabilityQuestion,
    ExperienceCatalog,
    ExperienceItem,
)
from app.domain.entities.tender import TenderItem
from app.infrastructure.services.gemini_proposal_service import GeminiProposalService
from tests.unit.application.test_score_tender_on_demand import crear_licitacion

SEC = CapabilityQuestion(
    question="¿Cuenta con certificación SEC clase A?",
    target_field="sec_clase_a",
    category="construccion",
    kind="certificacion",
    options=[
        CapabilityOption(label="Sí", polarity="afirmativa"),
        CapabilityOption(label="No", polarity="negativa"),
    ],
)
CATALOGO = ExperienceCatalog(
    items=[
        ExperienceItem(
            id="perfil:region:valparaiso",
            origin="perfil",
            kind="region",
            title="Región de operación",
            detail="Valparaíso",
        ),
        ExperienceItem(
            id=f"capacidad:{uuid4()}",
            origin="capacidad",
            kind="certificacion",
            title="¿Tiene ISO 9001?",
            detail="No",
            polarity="negativa",
        ),
    ]
)


def _licitacion():
    tender_id = uuid4()
    tender = crear_licitacion(tender_id)
    tender.description = "Instalación eléctrica en liceo. Deberá contar con SEC."
    tender.items = [
        TenderItem(
            tender_id=tender_id,
            product_code="72151500",
            name="Instalación eléctrica",
            quantity=1,
            unit_of_measure="Servicio",
        )
    ]
    return tender


def _respuesta(cuerpo: dict | str, status: int = 200) -> MagicMock:
    texto = cuerpo if isinstance(cuerpo, str) else json.dumps(cuerpo)
    respuesta = MagicMock(spec=httpx.Response)
    respuesta.status_code = status
    respuesta.text = texto
    respuesta.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": texto}]}}]
    }
    return respuesta


RESULTADO = {
    "requirements": [
        {
            "text": "Deberá contar con certificación SEC.",
            "kind": "certificacion",
            "mandatory": True,
            "origin": "Descripción",
            "question_key": "sec_clase_a",
        },
        {
            "text": "Entrega en Valparaíso.",
            "kind": "disponibilidad",
            "mandatory": True,
            "origin": "Ítem 1",
            "catalog_item_id": "perfil:region:valparaiso",
        },
        {
            "text": "Se valorará experiencia en colegios.",
            "kind": "experiencia",
            "mandatory": False,
            "origin": "bases.pdf",
            "new_question": {
                "question": "¿Tiene experiencia en instalaciones eléctricas en colegios?",
                "target_field": "experiencia:instalaciones-colegios",
                "kind": "experiencia_proyecto",
                "work_type": "instalaciones eléctricas en colegios",
            },
        },
    ],
    "requires_technical_document": True,
    "technical_document_reason": "Las bases piden una memoria técnica.",
}


async def _analizar(respuesta: MagicMock, documentos=None):
    servicio = GeminiProposalService(api_key="clave", model_name="modelo")
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
        post.return_value = respuesta
        resultado = await servicio.analyze_feasibility(
            tender=_licitacion(),
            catalog=CATALOGO,
            bank_questions=[SEC],
            documents=documentos or [],
        )
    return resultado, post


async def test_interpreta_las_exigencias_y_el_documento_tecnico():
    resultado, _ = await _analizar(_respuesta(RESULTADO))

    assert [r.text for r in resultado.requirements] == [
        "Deberá contar con certificación SEC.",
        "Entrega en Valparaíso.",
        "Se valorará experiencia en colegios.",
    ]
    assert resultado.requirements[0].question_key == "sec_clase_a"
    assert resultado.requirements[1].catalog_item_id == "perfil:region:valparaiso"
    nueva = resultado.requirements[2].new_question
    assert nueva is not None and nueva.kind == "experiencia_proyecto"
    assert resultado.requires_technical_document is True


async def test_el_prompt_lleva_la_ficha_el_catalogo_y_las_claves_del_banco():
    _, post = await _analizar(_respuesta(RESULTADO))

    _, kwargs = post.call_args
    texto = " ".join(p.get("text", "") for p in kwargs["json"]["contents"][0]["parts"])
    assert "Deberá contar con SEC" in texto
    assert "Instalación eléctrica" in texto
    assert "perfil:region:valparaiso" in texto
    assert "sec_clase_a" in texto
    # Las respuestas negativas también son datos: la IA las tiene que ver.
    assert "negativa" in texto
    assert kwargs["timeout"] == 60.0
    assert kwargs["json"]["generationConfig"]["responseMimeType"] == "application/json"
    assert kwargs["json"]["generationConfig"]["temperature"] == 0


async def test_manda_los_pdf_como_datos_en_linea_y_avisa_los_danados():
    documentos = [
        DocumentContextDTO(
            document_name="bases.pdf", file_type="pdf", file_bytes=b"%PDF"
        ),
        DocumentContextDTO(
            document_name="roto.pdf", file_type="pdf", file_bytes=b"", is_corrupted=True
        ),
    ]

    _, post = await _analizar(_respuesta(RESULTADO), documentos)

    partes = post.call_args.kwargs["json"]["contents"][0]["parts"]
    en_linea = [p["inlineData"] for p in partes if "inlineData" in p]
    assert en_linea == [{"mimeType": "application/pdf", "data": "JVBERg=="}]
    assert any(
        "roto.pdf" in p.get("text", "") and "DAÑADO" in p["text"] for p in partes
    )


async def test_un_error_http_es_un_error_del_servicio():
    with pytest.raises(ProposalAIServiceError):
        await _analizar(_respuesta({"error": "cuota"}, status=429))


async def test_un_json_invalido_es_un_error_del_servicio():
    with pytest.raises(ProposalAIServiceError):
        await _analizar(_respuesta("esto no es json"))


async def test_una_exigencia_con_forma_invalida_es_un_error_del_servicio():
    malo = {"requirements": [{"text": "x", "kind": "inventado", "mandatory": True}]}

    with pytest.raises(ProposalAIServiceError):
        await _analizar(_respuesta(malo))


async def test_un_error_de_conexion_es_un_error_del_servicio():
    servicio = GeminiProposalService(api_key="clave", model_name="modelo")
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
        post.side_effect = httpx.ConnectTimeout("lento")
        with pytest.raises(ProposalAIServiceError):
            await servicio.analyze_feasibility(
                tender=_licitacion(), catalog=CATALOGO, bank_questions=[], documents=[]
            )
