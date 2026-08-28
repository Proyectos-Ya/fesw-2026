from uuid import UUID

from app.application.repositories.saved_tender_repository import ISavedTenderRepository
from app.domain.errors.saved_tender_errors import SavedTenderNotFound


class UnsaveTenderUseCase:
    """Retira una licitación de la lista de guardadas del usuario autenticado."""

    def __init__(self, saved_tender_repo: ISavedTenderRepository):
        self.saved_tender_repo = saved_tender_repo

    async def execute(self, user_id: UUID, tender_id: UUID) -> None:
        deleted = await self.saved_tender_repo.delete(user_id, tender_id)
        if not deleted:
            raise SavedTenderNotFound(user_id, tender_id)
