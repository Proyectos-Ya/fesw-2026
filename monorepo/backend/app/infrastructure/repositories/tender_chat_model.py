from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class TenderChatSessionModel(SQLModel, table=True):
    """Modelo SQLModel para persistir sesiones de conversación del asistente."""
    __tablename__ = "tender_chat_sessions"  # type: ignore

    id: UUID = Field(primary_key=True)
    tender_id: UUID = Field(foreign_key="tender.id", index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    title: Optional[str] = Field(default=None, max_length=255)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime
    updated_at: datetime


class TenderChatMessageModel(SQLModel, table=True):
    """Modelo SQLModel para persistir mensajes del chat del asistente de licitaciones."""
    __tablename__ = "tender_chat_messages"  # type: ignore

    id: UUID = Field(primary_key=True)
    session_id: Optional[UUID] = Field(default=None, foreign_key="tender_chat_sessions.id", index=True)
    tender_id: UUID = Field(foreign_key="tender.id", index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    role: str = Field(max_length=20)
    content: str
    citations: List[dict] = Field(default=[], sa_column=Column(JSON))
    discrepancies: List[dict] = Field(default=[], sa_column=Column(JSON))
    warnings: List[str] = Field(default=[], sa_column=Column(JSON))
    unbacked_aspects: List[str] = Field(default=[], sa_column=Column(JSON))
    has_sufficient_info: bool = Field(default=True)
    created_at: datetime



class TenderChatDocumentModel(SQLModel, table=True):
    """Modelo SQLModel para persistir la metadata de documentos adjuntos al chat."""
    __tablename__ = "tender_chat_documents"  # type: ignore

    id: UUID = Field(primary_key=True)
    tender_id: UUID = Field(foreign_key="tender.id", index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    file_name: str = Field(max_length=255)
    file_type: str = Field(max_length=10)
    file_size_bytes: int
    storage_path: str
    created_at: datetime
