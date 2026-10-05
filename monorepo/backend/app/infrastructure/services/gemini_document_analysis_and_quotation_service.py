import base64
import json
import logging
from decimal import Decimal

import httpx

from app.application.services.document_analysis_quotation_service import (
    DocumentAnalysisAndQuotationResult,
    IDocumentAnalysisAndQuotationService,
)
from app.domain.entities.deep_analysis import (
    VALID_RECOMMENDATIONS,
    DeepAnalysis,
)
from app.domain.entities.quotation import MaterialItem, QuotationInput
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender
from app.domain.errors.document_analysis_quotation_errors import (
    DocumentAnalysisAndQuotationServiceError,
)
from app.infrastructure.services.document_text import xlsx_to_text
from app.shared.datetime_utils import utc_now_naive

logger = logging.getLogger(__name__)


class GeminiDocumentAnalysisAndQuotationService(IDocumentAnalysisAndQuotationService):
    """Servicio que invoca a Gemini en UNA SOLA llamada para generar DeepAnalysis y Quotation."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model_name = model_name

    def _build_prompt(
        self,
        tender: Tender,
        supplier: Supplier,
        file_name: str,
        matching_score: float | None = None,
    ) -> str:
        tender_items_str = ""
        for idx, item in enumerate(tender.items or []):
            tender_items_str += (
                f"- Ítem {idx + 1}: {item.name or ''} (Código: {item.product_code or ''}, "
                f"Cantidad: {item.quantity or 1}, Medida: {item.unit_of_measure or ''}). "
                f"Desc: {item.description or ''}\n"
            )

        tender_info = (
            f"Código: {tender.code or ''}\n"
            f"Título: {tender.name or ''}\n"
            f"Descripción: {tender.description or ''}\n"
            f"Institución Compradora: {tender.buyer_name or ''} ({tender.buyer_unit or ''})\n"
            f"Ítems requeridos en bases:\n{tender_items_str or 'No especificados en metadatos'}"
        )

        supplier_info = (
            f"Nombre Legal: {supplier.legal_name or ''} ({supplier.trade_name or ''})\n"
            f"Descripción del Perfil: {supplier.description or ''}\n"
            f"Regiones de Operación: {', '.join(supplier.regions or [])}\n"
            f"Sectores Industriales: {', '.join(supplier.sectors or [])}\n"
            f"Certificaciones del Proveedor: {', '.join(supplier.certifications or [])}\n"
            f"Palabras Clave: {', '.join(supplier.keywords or [])}\n"
            f"Años de Experiencia: {supplier.years_experience or 0}\n"
            f"Número de Empleados: {supplier.num_employees or 0}"
        )

        score_directive = (
            f"El porcentaje de compatibilidad de este proveedor para esta licitación es de exactamente {matching_score}%. "
            f"Este porcentaje fue pre-calculado por algoritmos del sistema. "
            f"En 'analysis.compatibility_score', DEBES devolver exactamente este valor ({matching_score}) sin alterarlo.\n"
            if matching_score is not None
            else "Evalúa y estima el porcentaje de compatibilidad global de 0 a 100 en 'analysis.compatibility_score'.\n"
        )

        return (
            f"[INSTRUCCIONES DEL SISTEMA]\n"
            f"Eres un analista experto en licitaciones de Mercado Público de Chile y cotizador técnico-comercial.\n"
            f"Tu misión es analizar conjuntamente los antecedentes de la licitación, el perfil de la empresa proveedora, "
            f"y el documento adjunto subido '{file_name}' para generar en una sola evaluación estructurada:\n"
            f"1. UN ANÁLISIS PROFUNDO DE COMPATIBILIDAD (analysis):\n"
            f"{score_directive}"
            f"- 'recommendation': Limítala estrictamente a uno de: 'Postular', 'Evaluar con cautela', 'No recomendado'.\n"
            f"- 'justification': Justificación fundamentada en español explicando la idoneidad técnica del proveedor frente a los requerimientos y el documento adjunto.\n\n"
            f"2. UNA COTIZACIÓN ESTIMADA (quotation):\n"
            f"- 'currency': Estrictamente 'CLP'.\n"
            f"- 'items': Lista de bienes, materiales o servicios solicitados en la licitación y detallados en el documento adjunto.\n"
            f"  Cada ítem debe tener:\n"
            f"  * 'description': Descripción del bien o servicio.\n"
            f"  * 'unit': Unidad de medida (ej. 'UN', 'rollo', 'caja', 'kg', 'GL').\n"
            f"  * 'quantity': Cantidad positiva requerida (> 0).\n"
            f"  * 'unit_price': Precio unitario estimado de mercado en pesos chilenos (>= 0).\n"
            f"  * 'subtotal': Subtotal de la línea (quantity * unit_price).\n"
            f"- 'total': Suma total de los subtotales en CLP.\n"
            f"- Si no se identifican partidas desglosadas en el documento o licitación, genera al menos una partida consolidada con el alcance global del servicio o suministro.\n\n"
            f"[DATOS DE LA LICITACIÓN]\n{tender_info}\n\n"
            f"[DATOS DEL PROVEEDOR]\n{supplier_info}\n"
        )

    async def analyze_and_quote(
        self,
        document_bytes: bytes,
        file_name: str,
        file_type: str,
        tender: Tender,
        supplier: Supplier,
        matching_score: float | None = None,
    ) -> DocumentAnalysisAndQuotationResult:
        normalized_type = file_type.lower().strip()
        parts: list[dict] = [
            {"text": self._build_prompt(tender, supplier, file_name, matching_score)}
        ]

        if normalized_type == "pdf":
            b64_data = base64.b64encode(document_bytes).decode("utf-8")
            parts.append({
                "inlineData": {
                    "mimeType": "application/pdf",
                    "data": b64_data,
                }
            })
            parts.append({"text": f"Documento adjunto analizado: '{file_name}'"})
        elif normalized_type == "png":
            b64_data = base64.b64encode(document_bytes).decode("utf-8")
            parts.append({
                "inlineData": {
                    "mimeType": "image/png",
                    "data": b64_data,
                }
            })
            parts.append({"text": f"Imagen/Plano adjunto analizado: '{file_name}'"})
        elif normalized_type == "xlsx":
            xlsx_text = xlsx_to_text(document_bytes, file_name)
            parts.append({"text": f"Contenido de planilla adjunta '{file_name}':\n{xlsx_text}"})
        else:
            parts.append({"text": f"Documento adjunto: '{file_name}' (tipo {file_type})"})

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT",
                    "properties": {
                        "analysis": {
                            "type": "OBJECT",
                            "properties": {
                                "compatibility_score": {
                                    "type": "NUMBER",
                                    "description": "Porcentaje de compatibilidad global de 0 a 100",
                                },
                                "recommendation": {
                                    "type": "STRING",
                                    "enum": ["Postular", "Evaluar con cautela", "No recomendado"],
                                    "description": "Recomendación estratégica para la postulación",
                                },
                                "justification": {
                                    "type": "STRING",
                                    "description": "Justificación clara y fundamentada",
                                },
                            },
                            "required": ["compatibility_score", "recommendation", "justification"],
                        },
                        "quotation": {
                            "type": "OBJECT",
                            "properties": {
                                "currency": {
                                    "type": "STRING",
                                    "enum": ["CLP"],
                                    "description": "Moneda de la cotización en CLP",
                                },
                                "items": {
                                    "type": "ARRAY",
                                    "description": "Lista de ítems cotizados",
                                    "items": {
                                        "type": "OBJECT",
                                        "properties": {
                                            "description": {"type": "STRING"},
                                            "unit": {"type": "STRING"},
                                            "quantity": {"type": "NUMBER"},
                                            "unit_price": {"type": "NUMBER"},
                                            "subtotal": {"type": "NUMBER"},
                                        },
                                        "required": ["description", "unit", "quantity", "unit_price", "subtotal"],
                                    },
                                },
                                "total": {"type": "NUMBER", "description": "Monto total estimado"},
                            },
                            "required": ["currency", "items", "total"],
                        },
                    },
                    "required": ["analysis", "quotation"],
                },
            },
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=60.0)
        except httpx.HTTPError as e:
            raise DocumentAnalysisAndQuotationServiceError(
                f"Error de conexión con la API de Gemini: {e}"
            ) from e

        if response.status_code != 200:
            raise DocumentAnalysisAndQuotationServiceError(
                f"Error en la API de Gemini (HTTP {response.status_code}): {response.text}"
            )

        try:
            resp_data = response.json()
            candidate = resp_data["candidates"][0]
            part = candidate["content"]["parts"][0]
            json_text = part["text"]
            result_json = json.loads(json_text)
            analysis_data = result_json["analysis"]
            quotation_data = result_json["quotation"]
        except (KeyError, IndexError, ValueError, json.JSONDecodeError) as e:
            raise DocumentAnalysisAndQuotationServiceError(
                f"No se pudo decodificar o estructurar la respuesta de Gemini: {e}. Respuesta: {response.text}"
            ) from e

        # 1. Parse DeepAnalysis
        score = (
            matching_score
            if matching_score is not None
            else float(analysis_data.get("compatibility_score", 0.0))
        )
        score = max(0.0, min(100.0, score))
        recommendation = str(analysis_data.get("recommendation", "Evaluar con cautela"))
        if recommendation not in VALID_RECOMMENDATIONS:
            recommendation = "Evaluar con cautela"
        justification = str(analysis_data.get("justification", ""))

        now = utc_now_naive()
        deep_analysis = DeepAnalysis(
            tender_id=tender.id,
            supplier_id=supplier.id,
            compatibility_score=score,
            recommendation=recommendation,  # type: ignore[arg-type]
            justification=justification,
            tender_updated_at=tender.updated_at,
            supplier_updated_at=supplier.updated_at,
            created_at=now,
            updated_at=now,
        )

        # 2. Parse QuotationInput
        raw_items = quotation_data.get("items", [])
        material_items: list[MaterialItem] = []
        for raw in raw_items:
            desc = str(raw.get("description", "")).strip()[:500]
            unit = str(raw.get("unit", "UN")).strip()[:40] or "UN"
            try:
                qty = Decimal(str(raw.get("quantity", 1)))
                if qty <= Decimal("0"):
                    qty = Decimal("1")
            except Exception:
                qty = Decimal("1")
            try:
                price = Decimal(str(raw.get("unit_price", 0)))
                if price < Decimal("0"):
                    price = Decimal("0")
            except Exception:
                price = Decimal("0")
            if desc:
                material_items.append(
                    MaterialItem(
                        description=desc,
                        unit=unit,
                        quantity=qty,
                        unit_price=price,
                    )
                )

        if not material_items:
            fallback_name = (tender.name or "Suministro / Servicio licitación").strip()[:400]
            material_items.append(
                MaterialItem(
                    description=fallback_name or "Servicio según bases",
                    unit="GL",
                    quantity=Decimal("1"),
                    unit_price=Decimal("0"),
                )
            )

        quotation_input = QuotationInput(
            currency="CLP",
            items=material_items,
        )

        return DocumentAnalysisAndQuotationResult(
            analysis=deep_analysis,
            quotation=quotation_input,
        )
