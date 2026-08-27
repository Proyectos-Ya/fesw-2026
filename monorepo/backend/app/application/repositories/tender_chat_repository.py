from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID
from app.domain.entities.tender_chat import (
    TenderChatMessage,
    TenderChatDocument,
    TenderChatSession,
)


class ITenderChatRepository(ABC):
    """Contrato del repositorio para persistir mensajes, documentos y sesiones del chat de licitación."""

    @abstractmethod
    async def create_session(
        self, user_id: UUID, tender_id: UUID, title: Optional[str] = None
    ) -> TenderChatSession:
        """Crea una nueva sesión activa de chat, desactivando las sesiones activas anteriores para esta licitación."""
        pass

    @abstractmethod
    async def get_or_create_active_session(
        self, user_id: UUID, tender_id: UUID
    ) -> TenderChatSession:
        """Obtiene la sesión activa actual o crea una nueva si no existe."""
        pass

    @abstractmethod
    async def get_session_by_id(
        self, session_id: UUID, user_id: UUID
    ) -> Optional[TenderChatSession]:
        """Obtiene una sesión puntual validando pertenencia al usuario."""
        pass

    @abstractmethod
    async def get_session_history(
        self, session_id: UUID, user_id: UUID, limit: int = 50
    ) -> List[TenderChatMessage]:
        """Obtiene los mensajes de una sesión específica en orden cronológico."""
        pass

    @abstractmethod
    async def archive_session(self, session_id: UUID, user_id: UUID) -> bool:
        """Archiva (desactiva) una sesión de chat."""
        pass

    @abstractmethod
    async def save_message(self, message: TenderChatMessage) -> TenderChatMessage:
        """Guarda un mensaje de chat (usuario o asistente) en la base de datos."""
        pass


    @abstractmethod
    async def get_history(self, user_id: UUID, tender_id: UUID, limit: int = 50) -> List[TenderChatMessage]:
        """Obtiene el historial cronológico de mensajes entre el usuario y el asistente para una licitación."""
        pass

    @abstractmethod
    async def save_document(self, doc: TenderChatDocument, file_bytes: bytes) -> TenderChatDocument:
        """Persiste los metadatos y el contenido binario del archivo adjunto al chat."""
        pass

    @abstractmethod
    async def get_documents_by_chat(self, user_id: UUID, tender_id: UUID) -> List[TenderChatDocument]:
        """Retorna la lista de documentos activos cargados por el usuario para esa licitación."""
        pass

    @abstractmethod
    async def get_document_bytes(self, document_id: UUID, user_id: UUID) -> Optional[bytes]:
        """Recupera los bytes del archivo para ser procesados por el motor de IA."""
        pass

    @abstractmethod
    async def delete_document(self, document_id: UUID, user_id: UUID) -> bool:
        """Elimina un documento adjunto y su archivo físico/almacenado."""
        pass
