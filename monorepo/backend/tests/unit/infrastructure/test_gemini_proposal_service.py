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
            "text": "Duración de 40 horas cronológicas.",
            "kind": "condicion",
            "mandatory": True,
            "origin": "Descripción",
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
        "Duración de 40 horas cronológicas.",
        "Se valorará experiencia en colegios.",
    ]
    assert resultado.requirements[2].kind == "condicion"
    assert resultado.requirements[0].question_key == "sec_clase_a"
    assert resultado.requirements[1].catalog_item_id == "perfil:region:valparaiso"
    nueva = resultado.requirements[3].new_question
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
    esquema = kwargs["json"]["generationConfig"]["responseSchema"]
    tipos = esquema["properties"]["requirements"]["items"]["properties"]["kind"]
    assert "condicion" in tipos["enum"]


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


async def test_reintenta_una_vez_si_gemini_esta_sobrecargado():
    """503 y 429 son pasajeros: un reintento evita un 502 innecesario."""
    servicio = GeminiProposalService(api_key="clave", model_name="modelo")
    with (
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        post.side_effect = [
            _respuesta({"error": "sobrecarga"}, 503),
            _respuesta(RESULTADO),
        ]
        resultado = await servicio.analyze_feasibility(
            tender=_licitacion(), catalog=CATALOGO, bank_questions=[], documents=[]
        )

    assert post.call_count == 2
    assert len(resultado.requirements) == 4


async def test_no_reintenta_un_error_que_no_es_pasajero():
    servicio = GeminiProposalService(api_key="clave", model_name="modelo")
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
        post.return_value = _respuesta({"error": "pedido inválido"}, 400)
        with pytest.raises(ProposalAIServiceError):
            await servicio.analyze_feasibility(
                tender=_licitacion(), catalog=CATALOGO, bank_questions=[], documents=[]
            )

    assert post.call_count == 1


async def test_si_el_reintento_tambien_falla_es_un_error_del_servicio():
    servicio = GeminiProposalService(api_key="clave", model_name="modelo")
    with (
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        post.return_value = _respuesta({"error": "sobrecarga"}, 503)
        with pytest.raises(ProposalAIServiceError):
            await servicio.analyze_feasibility(
                tender=_licitacion(), catalog=CATALOGO, bank_questions=[], documents=[]
            )

    assert post.call_count == 2


# --- Redacción del borrador (B4) -------------------------------------------

from app.domain.entities.proposal import ProposalWarning, Requirement  # noqa: E402

EXIGENCIAS = [
    Requirement(
        id="req-1",
        text="Duración de 40 horas cronológicas",
        kind="condicion",
        mandatory=True,
        origin="Descripción",
        status="cumple",
    ),
    Requirement(
        id="req-2",
        text="Deberá contar con certificación SEC.",
        kind="certificacion",
        mandatory=True,
        origin="Descripción",
        status="no_cumple",
    ),
]
ADVERTENCIAS = [
    ProposalWarning(
        requirement_id="req-2",
        text="Las bases exigen: certificación SEC. La empresa declaró no cumplirlo.",
    )
]
REDACCION = {
    "offer_name": {"paragraphs": [{"text": "Capacitación PAC", "source_ids": []}]},
    "offer_description": {
        "paragraphs": [
            {
                "text": "Operamos en Aysén.",
                "source_ids": ["perfil:region:valparaiso"],
                "asserts_company_fact": True,
            }
        ]
    },
    "required_documents": {"paragraphs": [{"text": "Cotización"}]},
    "technical_document": None,
}


async def _redactar(respuesta: MagicMock, **kwargs):
    servicio = GeminiProposalService(api_key="clave", model_name="modelo")
    datos = dict(
        tender=_licitacion(),
        requirements=EXIGENCIAS,
        catalog=CATALOGO,
        warnings=ADVERTENCIAS,
        include_technical_document=False,
        documents=[],
    )
    datos.update(kwargs)
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
        post.return_value = respuesta
        resultado = await servicio.generate_draft(**datos)
    return resultado, post


def _texto_del_prompt(post) -> str:
    partes = post.call_args.kwargs["json"]["contents"][0]["parts"]
    return " ".join(p.get("text", "") for p in partes)


async def test_redaccion_interpreta_secciones_y_fuentes():
    resultado, _ = await _redactar(_respuesta(REDACCION))

    assert resultado.offer_name.paragraphs[0].text == "Capacitación PAC"
    parrafo = resultado.offer_description.paragraphs[0]
    assert parrafo.source_ids == ["perfil:region:valparaiso"]
    assert parrafo.asserts_company_fact is True
    assert resultado.technical_document is None


async def test_redaccion_manda_exigencias_advertencias_y_catalogo():
    _, post = await _redactar(_respuesta(REDACCION))

    texto = _texto_del_prompt(post)
    assert "Duración de 40 horas cronológicas" in texto
    assert "no_cumple" in texto
    assert "La empresa declaró no cumplirlo" in texto
    assert "perfil:region:valparaiso" in texto
    assert "[[INSERTAR:" in texto
    assert post.call_args.kwargs["json"]["generationConfig"]["temperature"] > 0


async def test_redaccion_lista_los_documentos_ya_detectados_para_no_repetirlos():
    documento = Requirement(
        id="req-3",
        text="Adjuntar cotización",
        kind="documento",
        mandatory=True,
        origin="Descripción",
        status="cumple",
    )

    _, post = await _redactar(
        _respuesta(REDACCION), requirements=[*EXIGENCIAS, documento]
    )

    texto = _texto_del_prompt(post)
    assert "DOCUMENTOS YA DETECTADOS\n- Adjuntar cotización" in texto


async def test_redaccion_pide_documento_tecnico_solo_si_corresponde():
    _, sin = await _redactar(_respuesta(REDACCION), include_technical_document=False)
    _, con = await _redactar(_respuesta(REDACCION), include_technical_document=True)

    assert "NO redactes documento técnico" in _texto_del_prompt(sin)
    assert "SÍ redacta el documento técnico" in _texto_del_prompt(con)


async def test_redaccion_pide_las_secciones_fijas_del_documento_tecnico():
    con_tecnico = {
        **REDACCION,
        "technical_document": {
            "metodologia": {"paragraphs": [{"text": "Clases presenciales."}]},
            "otros": None,
        },
    }

    resultado, post = await _redactar(
        _respuesta(con_tecnico), include_technical_document=True
    )

    esquema = post.call_args.kwargs["json"]["generationConfig"]["responseSchema"]
    claves = esquema["properties"]["technical_document"]["properties"]
    assert list(claves) == [
        "antecedentes",
        "comprension",
        "metodologia",
        "plan_de_trabajo",
        "equipo",
        "otros",
    ]
    assert "plan_de_trabajo: Plan de trabajo y plazos" in _texto_del_prompt(post)
    tecnico = resultado.technical_document
    assert tecnico is not None
    assert tecnico.metodologia is not None
    assert tecnico.metodologia.paragraphs[0].text == "Clases presenciales."
    assert tecnico.equipo is None


async def test_redaccion_trata_las_instrucciones_como_datos_de_baja_prioridad():
    _, post = await _redactar(_respuesta(REDACCION), instructions="Tono más formal")

    texto = _texto_del_prompt(post)
    assert "Tono más formal" in texto
    assert "PRIORIDAD BAJA" in texto


async def test_redaccion_con_json_invalido_es_error_del_servicio():
    with pytest.raises(ProposalAIServiceError):
        await _redactar(_respuesta({"offer_name": "no es una sección"}))
