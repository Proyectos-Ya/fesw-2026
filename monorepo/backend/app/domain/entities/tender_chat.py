from datetime import datetime, timezone
from typing import Optional, List, Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator


def utc_now_naive() -> datetime:
    """Returns a timezone-naive UTC datetime to avoid timezone DB offset issues."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Citation(BaseModel):
    """Cita textual extraída del documento de la licitación."""
    document_name: str
    page_or_sheet: Optional[str] = None
    quote: str

    @field_validator("document_name", "quote")
    @classmethod
    def validate_not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("El campo no puede estar vacío.")
        return value.strip()


class TenderChatSession(BaseModel):
    """Representa una sesión o hilo de conversación independiente para una licitación."""
    id: UUID = Field(default_factory=uuid4)
    tender_id: UUID
    user_id: UUID
    title: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=utc_now_naive)
    updated_at: datetime = Field(default_factory=utc_now_naive)


class TenderChatMessage(BaseModel):
    """Representa un mensaje individual en la conversación del asistente."""
    id: UUID = Field(default_factory=uuid4)
    session_id: Optional[UUID] = None
    tender_id: UUID
    user_id: UUID
    role: Literal["user", "assistant"]
    content: str
    citations: List[Citation] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now_naive)


    @field_validator("content")
    @classmethod
    def validate_content_not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("El contenido del mensaje no puede estar vacío.")
        return value.strip()


class TenderChatDocument(BaseModel):
    """Metadatos del archivo subido en la conversación de la licitación."""
    id: UUID = Field(default_factory=uuid4)
    tender_id: UUID
    user_id: UUID
    file_name: str
    file_type: Literal["pdf", "xlsx", "png"]
    file_size_bytes: int = Field(gt=0, description="Tamaño del archivo en bytes, debe ser mayor a 0")
    storage_path: str
    created_at: datetime = Field(default_factory=utc_now_naive)

    @field_validator("file_name", "storage_path")
    @classmethod
    def validate_paths_not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("El nombre o ruta no puede estar vacío.")
        return value.strip()
