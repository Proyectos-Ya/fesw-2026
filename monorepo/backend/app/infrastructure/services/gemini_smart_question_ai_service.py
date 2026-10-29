import asyncio
import json
import logging
from typing import Any

import httpx
from pydantic import ValidationError

from app.application.services.smart_question_ai_service import (
    DynamicQuestionDTO,
    ISmartQuestionAIService,
)
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender

logger = logging.getLogger(__name__)

MAX_INTENTOS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 2.0
_ESTADOS_PASAJEROS = {429, 500, 502, 503, 504}


class SmartQuestionAIUnavailable(Exception):
    """Excepción lanzada cuando el servicio de IA de preguntas no está disponible."""

    pass


class _FallaPasajera(Exception):
    """Error transitorio que amerita reintento."""

    pass


_SMART_QUESTIONS_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "questions": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "question": {
                        "type": "STRING",
                        "description": (
                            "Pregunta estratégica y concisa formulada al proveedor (orientada a Sí/No) "
                            "sobre una exigencia clave de la licitación que no figure en su perfil."
                        ),
                    },
                    "target_keyword": {
                        "type": "STRING",
                        "description": (
                            "Palabra clave o tag técnico en formato 'categoria:detalle' "
                            "(ej: 'certificacion:iso_9001', 'maquinaria:grua_pluma', 'experiencia:obras_viales') "
                            "a inyectar al perfil si responde Sí."
                        ),
                    },
                    "options": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                        "description": "Opciones de respuesta disponibles (por defecto ['Sí', 'No']).",
                    },
                },
                "required": ["question", "target_keyword"],
            },
        }
    },
    "required": ["questions"],
}


class GeminiSmartQuestionAIService(ISmartQuestionAIService):
    """Implementación de generación de preguntas inteligentes utilizando Gemini Flash."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-1.5-flash",
        timeout_seconds: float = 60.0,
        retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.retry_backoff_seconds = retry_backoff_seconds

    async def generate_questions(
        self,
        tender: Tender,
        supplier: Supplier,
        attachment_texts: list[str],
        valid_negative_keywords: list[str],
    ) -> list[DynamicQuestionDTO]:
        prompt = self._build_prompt(
            tender=tender,
            supplier=supplier,
            attachment_texts=attachment_texts,
            valid_negative_keywords=valid_negative_keywords,
        )

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": _SMART_QUESTIONS_SCHEMA,
                "temperature": 0.2,
            },
        }

        elementos = await self._con_reintentos(payload)

        dtos: list[DynamicQuestionDTO] = []
        for item in elementos:
            try:
                dtos.append(DynamicQuestionDTO.model_validate(item))
            except ValidationError:
                logger.warning("Se omitió una pregunta mal formada devuelta por Gemini")

        return dtos

    def _build_prompt(
        self,
        tender: Tender,
        supplier: Supplier,
        attachment_texts: list[str],
        valid_negative_keywords: list[str],
    ) -> str:
        # Contexto de la licitación
        tender_ctx = (
            f"LICITACIÓN:\n"
            f"- Código: {tender.code}\n"
            f"- Título: {tender.name}\n"
            f"- Descripción: {tender.description or 'Sin descripción'}\n"
            f"- Comprador: {tender.buyer_name or ''} ({tender.buyer_unit or ''})\n"
        )
        if tender.items:
            items_desc = "\n".join(
                f"  * {it.name}: {it.description or ''} (Cant: {it.quantity})"
                for it in tender.items
            )
            tender_ctx += f"- Ítems / Productos solicitados:\n{items_desc}\n"

        # Contexto del proveedor
        supplier_ctx = (
            f"PERFIL ACTUAL DEL PROVEEDOR:\n"
            f"- Razón Social / Nombre: {supplier.legal_name} ({supplier.trade_name or ''})\n"
            f"- Descripción: {supplier.description or 'Sin descripción'}\n"
            f"- Sectores: {', '.join(supplier.sectors or [])}\n"
            f"- Certificaciones: {', '.join(supplier.certifications or [])}\n"
            f"- Palabras Clave actuales: {', '.join(supplier.keywords or [])}\n"
        )

        # Regla de Exclusiones (Memoria Negativa)
        if valid_negative_keywords:
            neg_text = (
                "REGLA CRÍTICA DE EXCLUSIONES (MEMORIA NEGATIVA):\n"
                "El proveedor ya ha indicado formalmente que NO posee las siguientes capacidades/certificaciones/recursos.\n"
                "ESTÁ ESTRICTAMENTE PROHIBIDO generar preguntas sobre cualquiera de estas temáticas:\n"
                + "\n".join(f"- {kw}" for kw in valid_negative_keywords)
                + "\n"
            )
        else:
            neg_text = "EXCLUSIONES PREVIAS: Ninguna.\n"

        # Contexto RAG de Bases / Documentos
        if attachment_texts:
            rag_text = (
                "BASES Y DOCUMENTOS ADJUNTOS DE LA LICITACIÓN (CONTEXTO RAG):\n"
                + "\n\n".join(attachment_texts)
                + "\n"
            )
        else:
            rag_text = "BASES ADJUNTAS: No se adjuntaron documentos de texto adicionales.\n"

        instructions = (
            "INSTRUCCIONES DEL SISTEMA:\n"
            "1. Eres un analista experto en licitaciones del Estado de Chile (Mercado Público).\n"
            "2. Tu misión es contrastar los requerimientos de la licitación y sus bases adjuntas con el perfil del proveedor.\n"
            "3. Identifica vacíos estratégicos o exigencias clave (certificaciones ISO/NCh, maquinaria o equipamiento especializado, registros MOP/MINVU, experiencia específica) indispensables para postular que NO figuren en el perfil del proveedor.\n"
            "4. Formula preguntas estratégicas orientadas a respuesta 'Sí' o 'No'.\n"
            "5. Cada pregunta debe definir un 'target_keyword' normalizado en minúsculas en formato 'categoria:detalle' (ej: 'certificacion:iso_9001', 'maquinaria:retroexcavadora_oruga', 'registro:mop_primera').\n"
            "6. CUMPLE ESTRICTAMENTE LA REGLA DE EXCLUSIONES DE MEMORIA NEGATIVA: NUNCA preguntes por capacidades descartadas.\n"
            "7. Basa tus preguntas prioritariamente en las exigencias y especificaciones técnicas encontradas en las bases adjuntas.\n"
            "8. REGLA DE NO REDUNDANCIA Y GRANULARIDAD:\n"
            "   - NO preguntes por capacidades, maquinaria o certificaciones que el proveedor YA posea en sus Palabras Clave o perfil actual.\n"
            "   - Si el proveedor ya cuenta con una categoría de maquinaria (ej: 'maquinaria:camion_pluma'), NO generes preguntas redundantes añadiendo sufijos de tonelaje, modelo o capacidad menor (ej: NO generar 'maquinaria:camion_pluma_15t' o 'maquinaria:camion_pluma_20t'). Se asume ya cubierto por la maquinaria existente.\n"
            "   - Los 'target_keyword' deben ser canónicos, limpios y reutilizables entre distintas licitaciones (ej: 'maquinaria:retroexcavadora_oruga', 'certificacion:iso_45001', 'seguridad:prevencionista_sns'). Evita sufijos de medidas particulares o números que ensucien el perfil.\n"
        )

        return f"{instructions}\n{neg_text}\n{tender_ctx}\n{supplier_ctx}\n{rag_text}"

    async def _con_reintentos(self, payload: dict[str, object]) -> list[object]:
        for intento in range(1, MAX_INTENTOS + 1):
            try:
                return await self._una_llamada(payload)
            except _FallaPasajera as falla:
                if intento == MAX_INTENTOS:
                    logger.error(
                        "Gemini no pudo generar preguntas tras %s intentos: %s",
                        MAX_INTENTOS,
                        falla,
                    )
                    raise SmartQuestionAIUnavailable() from falla
                logger.warning(
                    "Generación de preguntas, intento %s/%s fallido (%s); se reintenta",
                    intento,
                    MAX_INTENTOS,
                    falla,
                )
                if self.retry_backoff_seconds > 0:
                    await asyncio.sleep(self.retry_backoff_seconds * 2 ** (intento - 1))
        raise SmartQuestionAIUnavailable()

    async def _una_llamada(self, payload: dict[str, object]) -> list[object]:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_name}:generateContent"
        )
        try:
            async with httpx.AsyncClient() as client:
                respuesta = await client.post(
                    url,
                    json=payload,
                    headers={"x-goog-api-key": self.api_key},
                    timeout=self.timeout_seconds,
                )
        except httpx.HTTPError as error:
            raise _FallaPasajera(f"sin respuesta ({type(error).__name__})") from error

        if respuesta.status_code in _ESTADOS_PASAJEROS:
            raise _FallaPasajera(f"HTTP {respuesta.status_code}: {respuesta.text}")
        if respuesta.status_code != 200:
            logger.error(
                "Gemini rechazó la generación de preguntas (HTTP %s): %s",
                respuesta.status_code,
                respuesta.text,
            )
            raise SmartQuestionAIUnavailable()

        try:
            cuerpo = respuesta.json()
        except ValueError as error:
            raise _FallaPasajera("respuesta que no es JSON") from error

        return self._extraer_preguntas(cuerpo)

    def _extraer_preguntas(self, cuerpo: dict[str, Any]) -> list[object]:
        try:
            candidatos = cuerpo.get("candidates", [])
            if not candidatos:
                return []
            partes = candidatos[0].get("content", {}).get("parts", [])
            if not partes:
                return []
            texto = partes[0].get("text", "")
            data = json.loads(texto)
            preguntas = data.get("questions", [])
            if not isinstance(preguntas, list):
                return []
            return preguntas
        except (ValueError, KeyError, TypeError) as e:
            raise _FallaPasajera(f"error decodificando respuesta de Gemini: {e}") from e
