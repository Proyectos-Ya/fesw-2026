import base64
import json
from io import BytesIO

import httpx
import pytest
import respx

from app.application.services.tender_assistant_ai_service import DocumentContextDTO
from app.domain.errors.milestone_errors import MilestoneExtractionUnavailable
from app.infrastructure.services.gemini_milestone_extraction_service import (
    GeminiMilestoneExtractionService,
)

URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-test:generateContent?key=clave-test"
)
CONTEXTO = "Licitación: Reparación de techumbre. Cierre: 2026-10-20 15:00 (hora de Chile)."


@pytest.fixture
def service() -> GeminiMilestoneExtractionService:
    return GeminiMilestoneExtractionService(api_key="clave-test", model_name="gemini-test")


def _respuesta(hitos: list[dict[str, object]]) -> dict[str, object]:
    return {"candidates": [{"content": {"parts": [{"text": json.dumps({"hitos": hitos})}]}}]}


PDF = DocumentContextDTO(document_name="bases.pdf", file_type="pdf", file_bytes=b"%PDF-1.4 bases")


@respx.mock
async def test_envia_el_pdf_el_contexto_y_un_esquema_json(service):
    ruta = respx.post(URL).respond(200, json=_respuesta([]))

    await service.extract([PDF], CONTEXTO)

    cuerpo = json.loads(ruta.calls.last.request.content)
    partes = cuerpo["contents"][0]["parts"]
    textos = " ".join(p.get("text", "") for p in partes)
    assert {"inlineData": {"mimeType": "application/pdf", "data": base64.b64encode(b"%PDF-1.4 bases").decode()}} in partes
    assert "bases.pdf" in textos
    assert CONTEXTO in textos
    config = cuerpo["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    esquema_hito = config["responseSchema"]["properties"]["hitos"]["items"]
    assert "visita_tecnica" in esquema_hito["properties"]["kind"]["enum"]
    assert set(esquema_hito["required"]) >= {"kind", "title", "fecha"}


@respx.mock
async def test_la_instruccion_exige_fechas_iso_y_no_inventar(service):
    ruta = respx.post(URL).respond(200, json=_respuesta([]))

    await service.extract([PDF], CONTEXTO)

    instruccion = json.loads(ruta.calls.last.request.content)["contents"][0]["parts"][0]["text"]
    assert "YYYY-MM-DD" in instruccion
    assert "HH:MM" in instruccion
    assert "No inventes" in instruccion


@respx.mock
async def test_convierte_la_respuesta_en_hitos(service):
    respx.post(URL).respond(
        200,
        json=_respuesta(
            [
                {
                    "kind": "visita_tecnica",
                    "title": "Visita técnica obligatoria",
                    "description": "En el recinto municipal.",
                    "fecha": "2026-10-20",
                    "hora": "15:00",
                    "texto_original": "a las 15:00 del día 20",
                    "documento": "bases.pdf",
                },
                {"kind": "entrega", "title": "Entrega de muestras", "fecha": "2026-10-25"},
            ]
        ),
    )

    hitos = await service.extract([PDF], CONTEXTO)

    assert [h.title for h in hitos] == ["Visita técnica obligatoria", "Entrega de muestras"]
    assert hitos[0].hora == "15:00"
    assert hitos[0].texto_original == "a las 15:00 del día 20"
    assert hitos[0].documento == "bases.pdf"
    assert hitos[1].hora is None


@respx.mock
async def test_omite_elementos_mal_formados_sin_perder_los_buenos(service):
    respx.post(URL).respond(
        200,
        json=_respuesta(
            [
                {"kind": "entrega", "fecha": "2026-10-25"},  # sin título
                {"kind": "entrega", "title": "Entrega final", "fecha": "2026-10-30"},
            ]
        ),
    )

    hitos = await service.extract([PDF], CONTEXTO)

    assert [h.title for h in hitos] == ["Entrega final"]


@respx.mock
async def test_un_xlsx_viaja_como_texto(service):
    import openpyxl

    libro = openpyxl.Workbook()
    libro.active.append(["Hito", "Fecha"])  # type: ignore[union-attr]
    libro.active.append(["Visita a terreno", "20-10-2026"])  # type: ignore[union-attr]
    buffer = BytesIO()
    libro.save(buffer)
    ruta = respx.post(URL).respond(200, json=_respuesta([]))

    await service.extract(
        [DocumentContextDTO(document_name="cronograma.xlsx", file_type="xlsx", file_bytes=buffer.getvalue())],
        CONTEXTO,
    )

    partes = json.loads(ruta.calls.last.request.content)["contents"][0]["parts"]
    assert any("Visita a terreno" in p.get("text", "") for p in partes)
    assert not any("inlineData" in p for p in partes)


@respx.mock
@pytest.mark.parametrize(
    "respuesta",
    [
        httpx.Response(500, text="error interno"),
        httpx.Response(200, json={"candidates": []}),
        httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "no es json"}]}}]}),
    ],
)
async def test_errores_de_gemini_se_traducen_a_no_disponible(service, respuesta):
    respx.post(URL).mock(return_value=respuesta)

    with pytest.raises(MilestoneExtractionUnavailable):
        await service.extract([PDF], CONTEXTO)


@respx.mock
async def test_un_timeout_se_traduce_a_no_disponible(service):
    respx.post(URL).mock(side_effect=httpx.ReadTimeout("lento"))

    with pytest.raises(MilestoneExtractionUnavailable):
        await service.extract([PDF], CONTEXTO)
