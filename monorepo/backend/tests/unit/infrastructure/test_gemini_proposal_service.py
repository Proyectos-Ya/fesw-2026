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


async def test_factibilidad_pide_hasta_tres_preguntas_para_fortalecer_la_oferta():
    con_sugeridas = {
        **RESULTADO,
        "offer_questions": [
            {
                "text": "Experiencia en suministros a municipios",
                "kind": "experiencia",
                "mandatory": False,
                "origin": "Sugerida",
                "new_question": {
                    "question": "¿Tiene experiencia suministrando a municipios?",
                    "target_field": "experiencia:suministro-municipios",
                    "kind": "experiencia_proyecto",
                    "work_type": "suministro a municipios",
                },
            }
        ],
    }

    resultado, post = await _analizar(_respuesta(con_sugeridas))

    esquema = post.call_args.kwargs["json"]["generationConfig"]["responseSchema"]
    assert "offer_questions" in esquema["properties"]
    texto = " ".join(
        p.get("text", "") for p in post.call_args.kwargs["json"]["contents"][0]["parts"]
    )
    assert "offer_questions" in texto
    assert len(resultado.offer_questions) == 1


# --- Adjuntos primero (plan 292, §2.2) ---------------------------------------

DOCUMENTOS = [
    DocumentContextDTO(document_name="bases.pdf", file_type="pdf", file_bytes=b"%PDF"),
    DocumentContextDTO(
        document_name="roto.pdf", file_type="pdf", file_bytes=b"", is_corrupted=True
    ),
]


def _posiciones(post) -> tuple[list[int], int]:
    """Índices de las partes de los adjuntos y de la ficha en el mensaje."""
    partes = post.call_args.kwargs["json"]["contents"][0]["parts"]
    adjuntos = [
        i
        for i, p in enumerate(partes)
        if "inlineData" in p or p.get("text", "").startswith("Adjunto")
    ]
    [ficha] = [
        i
        for i, p in enumerate(partes)
        if p.get("text", "").startswith("## COMPRA ÁGIL")
    ]
    return adjuntos, ficha


async def test_factibilidad_manda_los_adjuntos_antes_que_la_ficha():
    _, post = await _analizar(_respuesta(RESULTADO), DOCUMENTOS)

    adjuntos, ficha = _posiciones(post)
    assert len(adjuntos) == 3
    assert max(adjuntos) < ficha
    # Las instrucciones siguen primero.
    assert min(adjuntos) == 1


async def test_redaccion_manda_los_adjuntos_antes_que_la_ficha():
    _, post = await _redactar(_respuesta(REDACCION), documents=DOCUMENTOS)

    adjuntos, ficha = _posiciones(post)
    assert len(adjuntos) == 3
    assert max(adjuntos) < ficha
    assert min(adjuntos) == 1


async def test_las_instrucciones_dicen_que_los_adjuntos_mandan():
    _, analisis = await _analizar(_respuesta(RESULTADO))
    _, redaccion = await _redactar(_respuesta(REDACCION))

    texto = _texto_del_prompt(analisis)
    assert "fuente principal" in texto
    assert "mandan" in texto
    assert "mentions_attachments" in texto
    assert "fallback_question" in texto
    assert "salen de los adjuntos" in _texto_del_prompt(redaccion)


async def test_factibilidad_pide_e_interpreta_respaldo_y_mencion_de_adjuntos():
    con_respaldo = {
        **RESULTADO,
        "mentions_attachments": True,
        "requirements": [
            {
                "text": "Experiencia en obras viales.",
                "kind": "experiencia",
                "mandatory": True,
                "origin": "bases.pdf",
                "catalog_item_id": "perfil:descripcion",
                "fallback_question": {
                    "question": "¿Tiene experiencia en obras viales?",
                    "target_field": "experiencia:obras-viales",
                    "kind": "experiencia_proyecto",
                    "work_type": "obras viales",
                },
            }
        ],
    }

    resultado, post = await _analizar(_respuesta(con_respaldo))

    esquema = post.call_args.kwargs["json"]["generationConfig"]["responseSchema"]
    propiedades = esquema["properties"]["requirements"]["items"]["properties"]
    assert propiedades["fallback_question"] == propiedades["new_question"]
    assert esquema["properties"]["mentions_attachments"] == {"type": "BOOLEAN"}
    assert "mentions_attachments" in esquema["required"]
    assert resultado.mentions_attachments is True
    respaldo = resultado.requirements[0].fallback_question
    assert respaldo is not None and respaldo.target_field == "experiencia:obras-viales"


async def test_sin_mencion_de_adjuntos_queda_en_falso():
    resultado, _ = await _analizar(_respuesta(RESULTADO))

    assert resultado.mentions_attachments is False


# --- presupuesto de tiempo (plan 292) -----------------------------------------
# Vercel corta un request reenviado a los 120 s. Los intentos a Gemini comparten
# un presupuesto total para que el backend responda antes de ese corte.


class _RelojFalso:
    """Devuelve los instantes indicados, uno por llamada; repite el último."""

    def __init__(self, *instantes: float):
        self._instantes = list(instantes)

    def __call__(self) -> float:
        if len(self._instantes) > 1:
            return self._instantes.pop(0)
        return self._instantes[0]


async def _analizar_con_reloj(reloj, respuestas):
    servicio = GeminiProposalService(api_key="clave", model_name="modelo", reloj=reloj)
    with (
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        post.side_effect = respuestas
        try:
            await servicio.analyze_feasibility(
                tender=_licitacion(), catalog=CATALOGO, bank_questions=[], documents=[]
            )
        except ProposalAIServiceError:
            pass
    return post


async def test_el_primer_intento_espera_hasta_60_segundos():
    post = await _analizar_con_reloj(_RelojFalso(0.0), [_respuesta(RESULTADO)])

    assert post.call_args.kwargs["timeout"] == 60.0


async def test_el_reintento_usa_solo_lo_que_queda_del_presupuesto():
    # Empieza en 0 y el primer intento vuelve con 503 a los 50 s. Tras 2 s de
    # espera quedan 100 - 52 = 48 s.
    post = await _analizar_con_reloj(
        _RelojFalso(0.0, 50.0, 52.0),
        [_respuesta({"error": "sobrecarga"}, 503), _respuesta(RESULTADO)],
    )

    assert post.call_count == 2
    assert post.call_args_list[1].kwargs["timeout"] == pytest.approx(48.0)


async def test_no_reintenta_si_queda_poco_presupuesto():
    # El 503 llega a los 85 s: un reintento no alcanzaría antes del corte.
    post = await _analizar_con_reloj(
        _RelojFalso(0.0, 85.0), [_respuesta({"error": "sobrecarga"}, 503)]
    )

    assert post.call_count == 1


async def test_sin_presupuesto_para_reintentar_es_un_error_del_servicio():
    servicio = GeminiProposalService(
        api_key="clave", model_name="modelo", reloj=_RelojFalso(0.0, 85.0)
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
        post.return_value = _respuesta({"error": "sobrecarga"}, 503)
        with pytest.raises(ProposalAIServiceError):
            await servicio.analyze_feasibility(
                tender=_licitacion(), catalog=CATALOGO, bank_questions=[], documents=[]
            )
