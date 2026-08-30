from typing import Optional
from uuid import UUID

from app.application.repositories.tender_chat_repository import ITenderChatRepository
from app.domain.entities.tender_chat import TenderChatSession


class CreateTenderChatSessionUseCase:
    """Crea una nueva sesión de chat limpia para una licitación (acción 'Nuevo Chat')."""

    def __init__(self, chat_repo: ITenderChatRepository):
        self.chat_repo = chat_repo

    async def execute(
        self,
        user_id: UUID,
        tender_id: UUID,
        title: Optional[str] = None,
    ) -> TenderChatSession:
        return await self.chat_repo.create_session(
            user_id=user_id,
            tender_id=tender_id,
            title=title,
        )
