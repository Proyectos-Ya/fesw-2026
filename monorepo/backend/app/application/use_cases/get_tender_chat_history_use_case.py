from typing import List
from uuid import UUID

from app.application.repositories.tender_chat_repository import ITenderChatRepository
from app.domain.entities.tender_chat import TenderChatMessage


class GetTenderChatHistoryUseCase:
    """Caso de uso para obtener el historial cronológico de mensajes del chat de una licitación."""

    def __init__(self, chat_repo: ITenderChatRepository):
        self.chat_repo = chat_repo

    async def execute(self, tender_id: UUID, user_id: UUID, limit: int = 50) -> List[TenderChatMessage]:
        return await self.chat_repo.get_history(user_id=user_id, tender_id=tender_id, limit=limit)
