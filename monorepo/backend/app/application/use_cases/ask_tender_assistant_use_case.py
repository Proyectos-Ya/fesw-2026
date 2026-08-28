from typing import List, Optional
from uuid import UUID

from app.application.repositories.tender_chat_repository import ITenderChatRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.services.document_validator_service import IDocumentValidatorService
from app.application.services.tender_assistant_ai_service import (
    ITenderAssistantAIService,
    DocumentContextDTO,
)
from app.domain.entities.tender_chat import TenderChatMessage
from app.domain.errors.tender_chat_errors import (
    TenderChatQueryTooLongError,
    TenderAssistantUnavailableError,
    InvalidPromptInstruction,
)


class AskTenderAssistantUseCase:
    """Caso de uso para realizar consultas al asistente virtual con RAG sobre documentos de la licitación y perfil de empresa."""

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
        validator_service: Optional[IDocumentValidatorService] = None,
    ):
        self.chat_repo = chat_repo
        self.ai_service = ai_service
        self.supplier_repo = supplier_repo
        self.validator_service = validator_service

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
        from app.domain.errors.tender_chat_errors import ChatSessionNotFoundError

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

        # 7. Obtener y validar documentos adjuntos asociados a esta licitación
        chat_docs = await self.chat_repo.get_documents_by_chat(
            user_id=user_id, tender_id=tender_id
        )
        document_contexts: List[DocumentContextDTO] = []
        unprocessed_warnings: List[str] = []

        for doc in chat_docs:
            raw_bytes = await self.chat_repo.get_document_bytes(doc.id, user_id)
            if not raw_bytes:
                unprocessed_warnings.append(
                    f"Advertencia: El documento '{doc.file_name}' no pudo ser recuperado del almacenamiento."
                )
                continue

            # Validar integridad técnica del archivo para aislar corruptos (CA6)
            if self.validator_service:
                val_result = self.validator_service.validate_integrity(
                    file_bytes=raw_bytes,
                    file_name=doc.file_name,
                    declared_type=doc.file_type,
                )
                if not val_result.is_valid:
                    unprocessed_warnings.append(
                        f"Advertencia: El documento '{doc.file_name}' está dañado o ilegible y no pudo ser procesado."
                    )
                    continue

            document_contexts.append(
                DocumentContextDTO(
                    document_name=doc.file_name,
                    file_type=doc.file_type,
                    file_bytes=raw_bytes,
                )
            )

        # 8. Obtener perfil de la empresa proveedora si existe
        supplier_context_str: Optional[str] = None
        if self.supplier_repo:
            try:
                supplier = await self.supplier_repo.get_by_user_id(user_id)
                if supplier:
                    supplier_context_str = (
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
            except Exception:
                supplier_context_str = None

        # 9. Invocar servicio de IA con historial multi-turn y documentos cruzados
        try:
            ai_response = await self.ai_service.generate_response(
                question=cleaned_question,
                history=history,
                documents=document_contexts,
                supplier_context=supplier_context_str,
            )

        except TenderAssistantUnavailableError:
            raise
        except Exception as e:
            raise TenderAssistantUnavailableError(
                f"El asistente virtual se encuentra temporalmente fuera de servicio: {e}"
            ) from e

        # 10. Crear y guardar mensaje de respuesta del asistente enriquecido
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
        saved_response = await self.chat_repo.save_message(assistant_msg)
        return saved_response


