from typing import Callable, List, Optional
from uuid import UUID
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)

from app.application.schemas.tender_chat_schema import (
    AskQuestionRequest,
    CreateChatSessionRequest,
    TenderChatSessionResponse,
    TenderChatMessageResponse,
    TenderChatDocumentResponse,
    CitationResponse,
    DiscrepancyResponse,
)
from app.domain.entities.tender_chat import (
    TenderChatMessage,
    TenderChatDocument,
    TenderChatSession,
)
from app.domain.entities.user import User
from app.domain.errors.tender_chat_errors import (
    TenderChatQueryTooLongError,
    TenderAssistantUnavailableError,
    UnsupportedDocumentTypeError,
    DocumentNotFoundError,
    MaxDocumentsExceededError,
    InvalidPromptInstruction,
    OutOfScopeQueryError,
    ChatSessionNotFoundError,
    ChatHistoryLoadError,
    CorruptedDocumentError,
    UnreadableDocumentError,
)


def create_tender_chat_router(
    get_current_user: Callable,
    get_upload_doc_use_case: Callable,
    get_list_docs_use_case: Callable,
    get_delete_doc_use_case: Callable,
    get_ask_assistant_use_case: Callable,
    get_chat_history_use_case: Callable,
    get_create_chat_session_use_case: Callable,
) -> APIRouter:
    router = APIRouter(prefix="/tenders/{tender_id}/assistant", tags=["Tender Assistant"])

    def _to_session_response(session: TenderChatSession) -> TenderChatSessionResponse:
        return TenderChatSessionResponse(
            id=session.id,
            tender_id=session.tender_id,
            user_id=session.user_id,
            title=session.title,
            is_active=session.is_active,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    def _to_doc_response(doc: TenderChatDocument) -> TenderChatDocumentResponse:
        return TenderChatDocumentResponse(
            id=doc.id,
            tender_id=doc.tender_id,
            file_name=doc.file_name,
            file_type=doc.file_type,
            file_size_bytes=doc.file_size_bytes,
            created_at=doc.created_at,
        )

    def _to_msg_response(msg: TenderChatMessage) -> TenderChatMessageResponse:
        citations = [
            CitationResponse(
                document_name=c.document_name,
                page_or_sheet=c.page_or_sheet,
                quote=c.quote,
            )
            for c in msg.citations
        ]
        discrepancies = [
            DiscrepancyResponse(
                topic=d.topic,
                description=d.description,
                conflicting_sources=[
                    CitationResponse(
                        document_name=cs.document_name,
                        page_or_sheet=cs.page_or_sheet,
                        quote=cs.quote,
                    )
                    for cs in d.conflicting_sources
                ]
            )
            for d in msg.discrepancies
        ]
        return TenderChatMessageResponse(
            id=msg.id,
            session_id=msg.session_id,
            tender_id=msg.tender_id,
            user_id=msg.user_id,
            role=msg.role,
            content=msg.content,
            citations=citations,
            discrepancies=discrepancies,
            warnings=msg.warnings,
            unbacked_aspects=msg.unbacked_aspects,
            has_sufficient_info=msg.has_sufficient_info,
            created_at=msg.created_at,
        )

    # 1. Crear nueva sesión de chat limpia ("Nuevo Chat")
    @router.post("/sessions", status_code=status.HTTP_201_CREATED, response_model=TenderChatSessionResponse)
    async def create_session(
        tender_id: UUID,
        body: Optional[CreateChatSessionRequest] = None,
        current_user: User = Depends(get_current_user),
        use_case = Depends(get_create_chat_session_use_case),
    ):
        try:
            session = await use_case.execute(
                user_id=current_user.id,
                tender_id=tender_id,
                title=body.title if body else None,
            )
            return _to_session_response(session)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    # 2. Cargar archivo adjunto al chat
    @router.post("/documents", status_code=status.HTTP_201_CREATED, response_model=TenderChatDocumentResponse)
    async def upload_document(
        tender_id: UUID,
        file: UploadFile = File(...),
        current_user: User = Depends(get_current_user),
        use_case = Depends(get_upload_doc_use_case),
    ):
        try:
            file_bytes = await file.read()
            doc = await use_case.execute(
                tender_id=tender_id,
                user_id=current_user.id,
                file_name=file.filename or "adjunto.pdf",
                file_bytes=file_bytes,
            )
            return _to_doc_response(doc)
        except (
            UnsupportedDocumentTypeError,
            MaxDocumentsExceededError,
            CorruptedDocumentError,
            UnreadableDocumentError,
            ValueError,
        ) as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    # 3. Listar documentos adjuntos del chat
    @router.get("/documents", response_model=List[TenderChatDocumentResponse])
    async def list_documents(
        tender_id: UUID,
        current_user: User = Depends(get_current_user),
        use_case = Depends(get_list_docs_use_case),
    ):
        docs = await use_case.execute(tender_id=tender_id, user_id=current_user.id)
        return [_to_doc_response(d) for d in docs]

    # 4. Eliminar documento adjunto del chat
    @router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_document(
        tender_id: UUID,
        document_id: UUID,
        current_user: User = Depends(get_current_user),
        use_case = Depends(get_delete_doc_use_case),
    ):
        try:
            await use_case.execute(document_id=document_id, user_id=current_user.id)
            return None
        except DocumentNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    # 5. Realizar consulta al asistente virtual
    @router.post("/ask", response_model=TenderChatMessageResponse)
    async def ask_assistant(
        tender_id: UUID,
        body: AskQuestionRequest,
        current_user: User = Depends(get_current_user),
        use_case = Depends(get_ask_assistant_use_case),
    ):
        try:
            msg = await use_case.execute(
                tender_id=tender_id,
                user_id=current_user.id,
                question=body.question,
                session_id=body.session_id,
            )
            return _to_msg_response(msg)
        except ChatSessionNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except TenderChatQueryTooLongError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except (InvalidPromptInstruction, OutOfScopeQueryError) as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except TenderAssistantUnavailableError as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # 6. Obtener historial del chat
    @router.get("/history", response_model=List[TenderChatMessageResponse])
    async def get_history(
        tender_id: UUID,
        session_id: Optional[UUID] = None,
        limit: int = 50,
        current_user: User = Depends(get_current_user),
        use_case = Depends(get_chat_history_use_case),
    ):
        try:
            messages = await use_case.execute(
                tender_id=tender_id,
                user_id=current_user.id,
                limit=limit,
                session_id=session_id,
            )
            return [_to_msg_response(m) for m in messages]
        except ChatSessionNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except ChatHistoryLoadError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return router

