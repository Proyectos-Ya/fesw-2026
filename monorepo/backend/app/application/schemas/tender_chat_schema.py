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
        description="Pregunta en lenguaje natural sobre la licitación (máximo 1000 caracteres)"
    )


class TenderChatMessageResponse(BaseModel):
    """Esquema de salida para un mensaje del chat."""
    id: UUID
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
