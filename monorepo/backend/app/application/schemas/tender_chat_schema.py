from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field


class CitationResponse(BaseModel):
    """Esquema de respuesta para una cita textual."""
    document_name: str
    page_or_sheet: Optional[str] = None
    quote: str


class AskQuestionRequest(BaseModel):
    """Esquema de entrada para realizar una pregunta al asistente."""
    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Pregunta en lenguaje natural sobre la licitación (máximo 1000 caracteres)",
    )
    session_id: Optional[UUID] = Field(
        default=None,
        description="ID de la sesión de chat a la que pertenece la pregunta (opcional, usa la activa por defecto)",
    )


class CreateChatSessionRequest(BaseModel):
    """Esquema de entrada para crear una nueva sesión de chat limpia."""
    title: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Título descriptivo opcional para la sesión de chat",
    )


class TenderChatSessionResponse(BaseModel):
    """Esquema de salida para una sesión de chat."""
    id: UUID
    tender_id: UUID
    user_id: UUID
    title: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TenderChatMessageResponse(BaseModel):
    """Esquema de salida para un mensaje del chat."""
    id: UUID
    session_id: Optional[UUID] = None
    tender_id: UUID
    user_id: UUID
    role: str
    content: str
    citations: List[CitationResponse] = Field(default_factory=list)
    created_at: datetime


class TenderChatDocumentResponse(BaseModel):
    """Esquema de salida para un documento adjunto al chat."""
    id: UUID
    tender_id: UUID
    file_name: str
    file_type: str
    file_size_bytes: int
    created_at: datetime

