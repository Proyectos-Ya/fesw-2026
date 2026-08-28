from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field

from app.domain.entities.tender_chat import TenderChatMessage, Citation


class AIResponseDTO(BaseModel):
    """Respuesta generada por el asistente con citas estructuradas."""

    answer: str
    citations: List[Citation] = Field(default_factory=list)
    has_sufficient_info: bool = True


class DocumentContextDTO(BaseModel):
    """Contexto de un documento cargado para el asistente."""

    document_name: str
    file_type: str  # "pdf" | "xlsx" | "png"
    file_bytes: bytes


class ITenderAssistantAIService(ABC):
    """Contrato del servicio de IA (Gemini) para responder consultas con RAG sobre documentos."""

    @abstractmethod
    async def generate_response(
        self,
        question: str,
        history: List[TenderChatMessage],
        documents: List[DocumentContextDTO],
        supplier_context: Optional[str] = None,
    ) -> AIResponseDTO:
        """
        Genera la respuesta a la pregunta del usuario utilizando el historial de chat,
        los documentos adjuntos y el perfil de la empresa consultante, extrayendo citas textuales exactas.
        """
        pass
