from uuid import UUID

from app.application.repositories.saved_tender_repository import (
    ISavedTenderRepository,
)
from app.domain.errors.saved_tender_errors import SavedTenderNotFound


class UnsaveTenderUseCase:
    """Retira una licitación de la lista del workspace (HU-18).

    Cualquier miembro del workspace puede desguardarla; no se restringe a quien
    la guardó originalmente.
    """

    def __init__(self, saved_tender_repo: ISavedTenderRepository):
        self.saved_tender_repo = saved_tender_repo

    async def execute(self, supplier_id: UUID, tender_id: UUID) -> None:
        deleted = await self.saved_tender_repo.delete(supplier_id, tender_id)
        if not deleted:
            raise SavedTenderNotFound(supplier_id, tender_id)
