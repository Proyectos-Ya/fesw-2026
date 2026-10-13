from abc import ABC, abstractmethod
from typing import List, Literal, Optional, Tuple
from uuid import UUID
from pydantic import BaseModel, Field

from app.domain.entities.tender_chat import (
    TenderChatMessage,
    Citation,
    DocumentDiscrepancy,
)


class AIResponseDTO(BaseModel):
    """Respuesta generada por el asistente con citas estructuradas, discrepancias y análisis de respaldo."""
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    discrepancies: List[DocumentDiscrepancy] = Field(default_factory=list)
    unbacked_aspects: List[str] = Field(default_factory=list)
    has_sufficient_info: bool = True


class DocumentContextDTO(BaseModel):
    """Contexto de un documento cargado para el asistente (compatible con RAG y legacy)."""
    document_name: str
    file_type: str  # "pdf" | "xlsx" | "png" | "docx" | "txt"
    file_bytes: bytes = b""
    text: str | None = None
    file_ref: str | None = None
    file_id: UUID | None = None
    source: Literal["panel", "legacy_chat"] = "panel"
    is_corrupted: bool = False


class ITenderAssistantAIService(ABC):
    """Contrato del servicio de IA (Gemini) para responder consultas con RAG sobre documentos."""

    @abstractmethod
    async def generate_response(
        self,
        question: str,
        history: List[TenderChatMessage],
        documents: List[DocumentContextDTO],
        supplier_context: Optional[str] = None,
        tender_context: Optional[str] = None,
        pass_number: int = 1,
    ) -> AIResponseDTO:
        """
        Genera la respuesta a la pregunta del usuario utilizando el historial de chat,
        los documentos adjuntos, el perfil de la empresa consultante y los metadatos e ítems de la licitación,
        extrayendo citas textuales exactas.
        """
        pass


