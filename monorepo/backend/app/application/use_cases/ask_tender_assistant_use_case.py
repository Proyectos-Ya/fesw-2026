import logging
from collections.abc import Callable
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from app.application.repositories.attachment_extraction_repository import (
    IAttachmentExtractionRepository,
)
from app.application.repositories.attachment_file_repository import (
    IAttachmentFileRepository,
)
from app.application.repositories.gemini_usage_repository import (
    IGeminiUsageRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_chat_repository import ITenderChatRepository
from app.application.repositories.tender_digest_repository import (
    ITenderDigestRepository,
)
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.services.assistant_context_builder import (
    construir_contexto_anexos,
    deduplicar_documentos_chat,
)
from app.application.services.attachment_storage import IAttachmentStorage
from app.application.services.document_validator_service import IDocumentValidatorService
from app.application.services.tender_assistant_ai_service import (
    DocumentContextDTO,
    ITenderAssistantAIService,
)
from app.application.use_cases.supplier.resolver_empresa import resolver_empresa
from app.domain.entities.attachment_extraction import EXTRACTION_PROMPT_VERSION, FuenteDeExtraccion
from app.domain.entities.tender_chat import TenderChatMessage
from app.domain.entities.tender_digest import TenderDigestData
from app.domain.errors.tender_chat_errors import (
    ChatSessionNotFoundError,
    InvalidPromptInstruction,
    TenderAssistantUnavailableError,
    TenderChatQueryTooLongError,
)
from app.infrastructure.services.document_text import xlsx_to_text
from app.shared.datetime_utils import chile_date, utc_now_naive

logger = logging.getLogger(__name__)

INLINE_MAX_BYTES = 15 * 1024 * 1024


def _extraer_texto_legacy(raw_bytes: bytes, file_name: str) -> str:
    if not raw_bytes:
        return ""
    ext = file_name.split(".")[-1].lower() if "." in file_name else ""
    if ext == "xlsx":
        try:
            return xlsx_to_text(raw_bytes, file_name)
        except Exception:
            return ""
    if ext in ("txt", "csv", "json"):
        try:
            return raw_bytes.decode("utf-8", errors="ignore")
        except Exception:
            return ""
    return ""


def _formatear_perfil_empresa(supplier) -> str:
    return (
        "=== ANTECEDENTES Y PERFIL DE LA EMPRESA QUE CONSULTA ===\n"
        f"- Razón Social: {supplier.legal_name}\n"
        f"- Nombre de Fantasía: {supplier.trade_name or 'N/A'}\n"
        f"- RUT: {supplier.rut}\n"
        f"- Años de Experiencia: {supplier.years_experience or 0} años\n"
        f"- Número de Empleados: {supplier.num_employees or 1}\n"
        f"- Regiones de Operación: {', '.join(supplier.regions or [])}\n"
        f"- Rubros / Sectores: {', '.join(supplier.sectors or [])}\n"
        f"- Certificaciones y Registros: {', '.join(supplier.certifications or [])}\n"
        f"- Palabras Clave de la Empresa: {', '.join(supplier.keywords or [])}\n"
        f"- Descripción de la Empresa: {supplier.description or 'Sin descripción'}\n"
    )


class AskTenderAssistantUseCase:
    """Caso de uso para realizar consultas al asistente virtual con RAG de dos pasadas sobre documentos oficiales y perfil."""

    MAX_QUERY_LENGTH = 1000
    FORBIDDEN_PROMPT_PATTERNS = [
        "ignora las instrucciones",
        "ignora los requisitos",
        "ignora tus instrucciones",
        "ignorar las instrucciones",
        "ignore instructions",
        "ignore previous instructions",
        "ignore all instructions",
        "system prompt",
        "revela tu prompt",
        "dame tu prompt",
        "show your prompt",
        "override instructions",
        "anula las instrucciones",
        "olvida tus restricciones",
        "forget your instructions",
        "act as dan",
        "jailbreak",
        "pretend you are",
        "simula ser",
        "tu nuevo rol es",
        "your new role is",
    ]

    def __init__(
        self,
        chat_repo: ITenderChatRepository,
        ai_service: ITenderAssistantAIService,
        supplier_repo: Optional[ISupplierRepository] = None,
        tender_repo: Optional[ITenderRepository] = None,
        validator_service: Optional[IDocumentValidatorService] = None,
        digest_repo: Optional[ITenderDigestRepository] = None,
        extraction_repo: Optional[IAttachmentExtractionRepository] = None,
        attachment_file_repo: Optional[IAttachmentFileRepository] = None,
        attachment_storage: Optional[IAttachmentStorage] = None,
        usage_repo: Optional[IGeminiUsageRepository] = None,
        daily_budget: int = 100,
        now_fn: Callable[[], datetime] = utc_now_naive,
    ):
        self.chat_repo = chat_repo
        self.ai_service = ai_service
        self.supplier_repo = supplier_repo
        self.tender_repo = tender_repo
        self.validator_service = validator_service
        self.digest_repo = digest_repo
        self.extraction_repo = extraction_repo
        self.attachment_file_repo = attachment_file_repo
        self.attachment_storage = attachment_storage
        self.usage_repo = usage_repo
        self.daily_budget = daily_budget
        self.now_fn = now_fn

    def _validate_guardrails(self, question: str) -> None:
        """Valida sintáctica y preventivamente intentos de manipulación del asistente (Prompt Injection)."""
        lowered = question.lower().strip()
        for pattern in self.FORBIDDEN_PROMPT_PATTERNS:
            if pattern in lowered:
                raise InvalidPromptInstruction(
                    f"Se detectó un intento de manipulación del prompt (Prompt Injection) mediante el patrón: '{pattern}'."
                )

    async def execute(
        self,
        tender_id: UUID,
        user_id: UUID,
        question: str,
        session_id: Optional[UUID] = None,
        supplier_id: UUID | None = None,
    ) -> TenderChatMessage:
        # 1. Validar pregunta no vacía
        cleaned_question = question.strip() if question else ""
        if not cleaned_question:
            raise ValueError("La consulta no puede estar vacía.")

        # 2. Validar longitud máxima de 1000 caracteres (Criterio HU-004)
        if len(cleaned_question) > self.MAX_QUERY_LENGTH:
            raise TenderChatQueryTooLongError()

        # 3. Validar guardarraíles de seguridad (Anti-Prompt Injection)
        self._validate_guardrails(cleaned_question)

        # 4. Resolver o validar la sesión de chat activa
        if session_id is not None:
            session = await self.chat_repo.get_session_by_id(
                session_id=session_id, user_id=user_id
            )
            if not session or session.tender_id != tender_id:
                raise ChatSessionNotFoundError(
                    "La sesión de chat no existe o no pertenece a esta licitación."
                )
        else:
            session = await self.chat_repo.get_or_create_active_session(
                user_id=user_id, tender_id=tender_id
            )
            session_id = session.id

        # 5. Obtener historial reciente de esta sesión específica
        history = await self.chat_repo.get_session_history(
            session_id=session_id, user_id=user_id, limit=20
        )

        # 6. Guardar mensaje de la pregunta del usuario asociado a la sesión
        user_msg = TenderChatMessage(
            session_id=session_id,
            tender_id=tender_id,
            user_id=user_id,
            role="user",
            content=cleaned_question,
        )
        await self.chat_repo.save_message(user_msg)

        # 7. Resolver empresa activa (Garantía de privacidad D5-5)
        supplier_context_str: Optional[str] = None
        workspace_id: Optional[UUID] = None
        if self.supplier_repo:
            try:
                supplier = await resolver_empresa(
                    self.supplier_repo, user_id, supplier_id
                )
                if supplier:
                    workspace_id = supplier.id
                    supplier_context_str = _formatear_perfil_empresa(supplier)
            except Exception:
                pass

        # 8. Obtener información general y metadatos de la licitación si existe
        tender_context_str: Optional[str] = None
        if self.tender_repo:
            try:
                tenders = await self.tender_repo.get_tenders(
                    TenderFilters(ids=[tender_id])
                )
                if tenders:
                    tender = tenders[0]
                    items_lines = []
                    for idx, it in enumerate(tender.items, 1):
                        item_desc = f" - {it.description}" if it.description else ""
                        items_lines.append(
                            f"  * Ítem {idx}: [{it.product_code}] {it.name} | Cantidad: {it.quantity} {it.unit_of_measure}{item_desc}"
                        )
                    items_str = (
                        "\n".join(items_lines)
                        if items_lines
                        else "  (No se detallan ítems específicos)"
                    )

                    amount_str = (
                        f"${tender.available_amount_clp:,.0f} CLP"
                        if tender.available_amount_clp is not None
                        else "No especificado"
                    )
                    pub_date_str = (
                        tender.published_at.strftime("%d/%m/%Y %H:%M")
                        if tender.published_at
                        else "N/A"
                    )
                    close_date_str = (
                        tender.closing_at.strftime("%d/%m/%Y %H:%M")
                        if tender.closing_at
                        else "N/A"
                    )

                    tender_context_str = (
                        "=== INFORMACIÓN GENERAL Y METADATOS DE LA LICITACIÓN ===\n"
                        f"- Código de Licitación: {tender.code}\n"
                        f"- Nombre / Título: {tender.name}\n"
                        f"- Descripción / Detalle: {tender.description or 'Sin descripción adicional'}\n"
                        f"- Estado: {tender.status_code or 'Publicada'}\n"
                        f"- Organismo Comprador: {tender.buyer_name or 'N/A'} (RUT: {tender.buyer_rut})\n"
                        f"- Unidad de Compra: {tender.buyer_unit}\n"
                        f"- Región: {tender.region or 'N/A'}\n"
                        f"- Comuna: {tender.commune or 'N/A'}\n"
                        f"- Presupuesto Estimado / Monto Disponible: {amount_str}\n"
                        f"- Fecha de Publicación: {pub_date_str}\n"
                        f"- Fecha de Cierre de Ofertas: {close_date_str}\n"
                        f"- Ítems y Productos Solicitados ({len(tender.items)}):\n{items_str}\n"
                    )
            except Exception:
                tender_context_str = None

        # 9. Obtener digest y fuentes oficiales del panel (Decisión 4 y 5)
        digest_data: Optional[TenderDigestData] = None
        panel_sources: list[FuenteDeExtraccion] = []
        if self.digest_repo:
            digest_entity = await self.digest_repo.get_current(tender_id, workspace_id)
            if digest_entity:
                digest_data = digest_entity.data

        if self.extraction_repo:
            panel_sources = await self.extraction_repo.list_sources(
                tender_id=tender_id,
                workspace_id=workspace_id,
                prompt_version=EXTRACTION_PROMPT_VERSION,
            )

        # 10. Obtener y fusionar documentos legacy de chat (D5-6)
        chat_docs = await self.chat_repo.get_documents_by_chat(user_id=user_id, tender_id=tender_id)
        chat_bytes_by_id: dict[UUID, bytes] = {}
        for d in chat_docs:
            b = await self.chat_repo.get_document_bytes(d.id, user_id)
            if b:
                chat_bytes_by_id[d.id] = b

        docs_legacy_unicos = deduplicar_documentos_chat(chat_docs, chat_bytes_by_id, panel_sources)
        legacy_con_texto = [
            (d, _extraer_texto_legacy(chat_bytes_by_id.get(d.id, b""), d.file_name))
            for d in docs_legacy_unicos
        ]

        # 11. Construir contexto consolidado de anexos para Pase 1
        anexos_texto = construir_contexto_anexos(digest_data, panel_sources, legacy_con_texto)
        unprocessed_warnings: List[str] = []

        document_contexts_p1: List[DocumentContextDTO] = []
        if digest_data or panel_sources:
            document_contexts_p1.append(
                DocumentContextDTO(
                    document_name="Resumen de Anexos y Bases Oficiales",
                    file_type="txt",
                    file_bytes=b"",
                    text=anexos_texto,
                    source="panel",
                )
            )

        for d, txt in legacy_con_texto:
            is_corrupted = False
            raw_b = chat_bytes_by_id.get(d.id, b"")
            if self.validator_service and raw_b:
                validation = self.validator_service.validate_integrity(
                    raw_b, d.file_name, d.file_type
                )
                if not validation.is_valid:
                    is_corrupted = True
                    unprocessed_warnings.append(
                        f"Advertencia: El documento '{d.file_name}' está dañado o su texto es ilegible y no fue posible procesarlo."
                    )
            document_contexts_p1.append(
                DocumentContextDTO(
                    document_name=d.file_name,
                    file_type=d.file_type,
                    file_bytes=b"" if is_corrupted else raw_b,
                    text=txt if not is_corrupted else "",
                    source="legacy_chat",
                    is_corrupted=is_corrupted,
                )
            )

        if not document_contexts_p1:
            document_contexts_p1.append(
                DocumentContextDTO(
                    document_name="Resumen de Anexos y Bases Oficiales",
                    file_type="txt",
                    file_bytes=b"",
                    text=anexos_texto,
                    source="panel",
                )
            )

        # 12. PASE 1: Generar respuesta con IA (Zero Bytes crudos)
        try:
            ai_response = await self.ai_service.generate_response(
                question=cleaned_question,
                history=history,
                documents=document_contexts_p1,
                supplier_context=supplier_context_str,
                tender_context=tender_context_str,
                pass_number=1,
            )
        except TenderAssistantUnavailableError:
            raise
        except Exception as e:
            raise TenderAssistantUnavailableError(
                f"El asistente virtual se encuentra temporalmente fuera de servicio: {e}"
            ) from e

        # 13. PASE 2 CONDICIONAL (D5-1 y D5-4):
        if not ai_response.has_sufficient_info:
            ahora = self.now_fn()
            dia_chile = chile_date(ahora)
            puede_llamar = True

            if self.usage_repo and self.daily_budget > 0:
                puede_llamar = await self.usage_repo.try_reserve_call(day=dia_chile, limit=self.daily_budget)

            if not puede_llamar:
                unprocessed_warnings.append(
                    "Aviso de cupo: La consulta requería inspeccionar los archivos originales completos, "
                    "pero se ha alcanzado el límite diario de consultas a la IA. La respuesta se basó exclusivamente "
                    "en el resumen disponible de las bases."
                )
            elif self.attachment_storage:
                document_contexts_p2: List[DocumentContextDTO] = []
                for fuente in panel_sources:
                    storage_key = getattr(fuente, "storage_key", None)
                    if not storage_key and self.attachment_file_repo:
                        file_id = getattr(fuente, "archivo_id", getattr(fuente, "attachment_file_id", None))
                        if file_id:
                            af = await self.attachment_file_repo.get(file_id)
                            if af:
                                storage_key = af.storage_key
                    if storage_key:
                        try:
                            raw_bytes = await self.attachment_storage.get_bytes(storage_key)
                            if len(raw_bytes) <= INLINE_MAX_BYTES:
                                document_contexts_p2.append(
                                    DocumentContextDTO(
                                        document_name=fuente.documento,
                                        file_type=fuente.documento.split(".")[-1].lower(),
                                        file_bytes=raw_bytes,
                                        file_ref=storage_key,
                                        source="panel",
                                    )
                                )
                        except Exception as e:
                            logger.warning("No se pudieron obtener bytes para %s: %s", fuente.documento, e)

                for d in docs_legacy_unicos:
                    raw_b = chat_bytes_by_id.get(d.id, b"")
                    if raw_b and len(raw_b) <= INLINE_MAX_BYTES:
                        document_contexts_p2.append(
                            DocumentContextDTO(
                                document_name=d.file_name,
                                file_type=d.file_type,
                                file_bytes=raw_b,
                                source="legacy_chat",
                            )
                        )

                if document_contexts_p2:
                    try:
                        ai_response_p2 = await self.ai_service.generate_response(
                            question=cleaned_question,
                            history=history,
                            documents=document_contexts_p2,
                            supplier_context=supplier_context_str,
                            tender_context=tender_context_str,
                            pass_number=2,
                        )
                        ai_response = ai_response_p2
                    except Exception as e:
                        logger.warning("Fallo en segunda pasada de IA, se conserva primera pasada: %s", e)

        # 14. Guardar y retornar mensaje final
        assistant_msg = TenderChatMessage(
            session_id=session_id,
            tender_id=tender_id,
            user_id=user_id,
            role="assistant",
            content=ai_response.answer,
            citations=ai_response.citations,
            discrepancies=ai_response.discrepancies,
            warnings=unprocessed_warnings,
            unbacked_aspects=ai_response.unbacked_aspects,
            has_sufficient_info=ai_response.has_sufficient_info,
        )
        return await self.chat_repo.save_message(assistant_msg)
