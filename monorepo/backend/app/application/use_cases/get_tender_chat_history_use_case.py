from typing import List, Optional
from uuid import UUID

from app.application.repositories.tender_chat_repository import ITenderChatRepository
from app.domain.entities.tender_chat import TenderChatMessage
from app.domain.errors.tender_chat_errors import ChatSessionNotFoundError


class GetTenderChatHistoryUseCase:
    """Caso de uso para obtener el historial cronológico de mensajes del chat de una licitación."""

    def __init__(self, chat_repo: ITenderChatRepository):
        self.chat_repo = chat_repo

    async def execute(
        self,
        tender_id: UUID,
        user_id: UUID,
        limit: int = 50,
        session_id: Optional[UUID] = None,
    ) -> List[TenderChatMessage]:
        if session_id is not None:
            session = await self.chat_repo.get_session_by_id(
                session_id=session_id, user_id=user_id
            )
            if not session or session.tender_id != tender_id:
                raise ChatSessionNotFoundError(
                    "La sesión de chat no existe o no pertenece a esta licitación."
                )
            return await self.chat_repo.get_session_history(
                session_id=session_id, user_id=user_id, limit=limit
            )

        return await self.chat_repo.get_history(
            user_id=user_id, tender_id=tender_id, limit=limit
        )

