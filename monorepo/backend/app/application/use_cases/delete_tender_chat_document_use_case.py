from uuid import UUID

from app.application.repositories.tender_chat_repository import ITenderChatRepository
from app.domain.errors.tender_chat_errors import DocumentNotFoundError


class DeleteTenderChatDocumentUseCase:
    """Caso de uso para eliminar un documento adjunto al chat de una licitación."""

    def __init__(self, chat_repo: ITenderChatRepository):
        self.chat_repo = chat_repo

    async def execute(self, document_id: UUID, user_id: UUID) -> bool:
        deleted = await self.chat_repo.delete_document(document_id=document_id, user_id=user_id)
        if not deleted:
            raise DocumentNotFoundError()
        return True
