from typing import List, Optional
from uuid import UUID

from app.application.repositories.tender_chat_repository import ITenderChatRepository
from app.application.services.tender_assistant_ai_service import (
    ITenderAssistantAIService,
    DocumentContextDTO,
)
from app.domain.entities.tender_chat import TenderChatMessage
from app.domain.errors.tender_chat_errors import (
    TenderChatQueryTooLongError,
    TenderAssistantUnavailableError,
)


class AskTenderAssistantUseCase:
    """Caso de uso para realizar consultas al asistente virtual con RAG sobre documentos de la licitación."""

    MAX_QUERY_LENGTH = 1000

    def __init__(
        self,
        chat_repo: ITenderChatRepository,
        ai_service: ITenderAssistantAIService,
    ):
        self.chat_repo = chat_repo
        self.ai_service = ai_service

    async def execute(
        self,
        tender_id: UUID,
        user_id: UUID,
        question: str,
    ) -> TenderChatMessage:
        # 1. Validar pregunta no vacía
        cleaned_question = question.strip() if question else ""
        if not cleaned_question:
            raise ValueError("La consulta no puede estar vacía.")

        # 2. Validar longitud máxima de 1000 caracteres (Criterio HU-004)
        if len(cleaned_question) > self.MAX_QUERY_LENGTH:
            raise TenderChatQueryTooLongError()

        # 3. Guardar mensaje de la pregunta del usuario
        user_msg = TenderChatMessage(
            tender_id=tender_id,
            user_id=user_id,
            role="user",
            content=cleaned_question,
        )
        await self.chat_repo.save_message(user_msg)

        # 4. Obtener historial reciente para dar contexto de conversación
        history = await self.chat_repo.get_history(user_id=user_id, tender_id=tender_id, limit=20)

        # 5. Obtener documentos adjuntos asociados a este chat/licitación
        chat_docs = await self.chat_repo.get_documents_by_chat(user_id=user_id, tender_id=tender_id)
        document_contexts: List[DocumentContextDTO] = []
        for doc in chat_docs:
            raw_bytes = await self.chat_repo.get_document_bytes(doc.id, user_id)
            if raw_bytes:
                document_contexts.append(
                    DocumentContextDTO(
                        document_name=doc.file_name,
                        file_type=doc.file_type,
                        file_bytes=raw_bytes,
                    )
                )

        # 6. Invocar servicio de IA
        try:
            ai_response = await self.ai_service.generate_response(
                question=cleaned_question,
                history=history,
                documents=document_contexts,
            )
        except TenderAssistantUnavailableError:
            raise
        except Exception as e:
            raise TenderAssistantUnavailableError(
                f"El asistente virtual se encuentra temporalmente fuera de servicio: {e}"
            ) from e

        # 7. Crear y guardar mensaje de respuesta del asistente
        assistant_msg = TenderChatMessage(
            tender_id=tender_id,
            user_id=user_id,
            role="assistant",
            content=ai_response.answer,
            citations=ai_response.citations,
        )
        saved_response = await self.chat_repo.save_message(assistant_msg)
        return saved_response
