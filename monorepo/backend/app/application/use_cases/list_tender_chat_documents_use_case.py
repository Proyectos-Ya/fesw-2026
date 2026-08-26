from typing import List
from uuid import UUID

from app.application.repositories.tender_chat_repository import ITenderChatRepository
from app.domain.entities.tender_chat import TenderChatDocument


class ListTenderChatDocumentsUseCase:
    """Caso de uso para listar los documentos activos asociados al chat de una licitación."""

    def __init__(self, chat_repo: ITenderChatRepository):
        self.chat_repo = chat_repo

    async def execute(self, tender_id: UUID, user_id: UUID) -> List[TenderChatDocument]:
        return await self.chat_repo.get_documents_by_chat(user_id=user_id, tender_id=tender_id)
