from uuid import UUID

from app.application.repositories.saved_tender_repository import ISavedTenderRepository
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.domain.entities.saved_tender import SavedTender
from app.domain.errors.tender_errors import TenderNotFound


class SaveTenderUseCase:
    """Marca una licitación como de interés para el usuario autenticado."""

    def __init__(
        self,
        saved_tender_repo: ISavedTenderRepository,
        tender_repo: ITenderRepository,
    ):
        self.saved_tender_repo = saved_tender_repo
        self.tender_repo = tender_repo

    async def execute(self, user_id: UUID, tender_id: UUID) -> SavedTender:
        tenders = await self.tender_repo.get_tenders(TenderFilters(ids=[tender_id]))
        if not tenders:
            raise TenderNotFound(tender_id)

        # Idempotente: el ícono de guardar puede dispararse dos veces (doble clic
        # o reintento tras un error de red) y eso no debe duplicar la fila.
        existing = await self.saved_tender_repo.get(user_id, tender_id)
        if existing is not None:
            return existing

        return await self.saved_tender_repo.save(
            SavedTender(user_id=user_id, tender_id=tender_id)
        )
