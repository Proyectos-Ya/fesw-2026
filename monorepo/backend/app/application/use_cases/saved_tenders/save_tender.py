from uuid import UUID

from app.application.repositories.saved_tender_repository import (
    ISavedTenderRepository,
)
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.domain.entities.saved_tender import SavedTender
from app.domain.errors.tender_errors import TenderNotFound


class SaveTenderUseCase:
    """Marca una licitación como de interés para el workspace (HU-18).

    Idempotente a nivel de workspace: si otro miembro ya la guardó, devuelve
    la fila existente sin levantar error. `user_id` queda registrado solo
    como auditoría ("quién la guardó primero").
    """

    def __init__(
        self,
        saved_tender_repo: ISavedTenderRepository,
        tender_repo: ITenderRepository,
    ):
        self.saved_tender_repo = saved_tender_repo
        self.tender_repo = tender_repo

    async def execute(
        self, supplier_id: UUID, user_id: UUID, tender_id: UUID
    ) -> SavedTender:
        tenders = await self.tender_repo.get_tenders(TenderFilters(ids=[tender_id]))
        if not tenders:
            raise TenderNotFound(tender_id)

        # Idempotente también a nivel de aplicación: evita escribir dos veces
        # si el repo subyacente aún no implementa ON CONFLICT DO NOTHING.
        existing = await self.saved_tender_repo.get(supplier_id, tender_id)
        if existing is not None:
            return existing

        return await self.saved_tender_repo.save(
            SavedTender(
                supplier_id=supplier_id, user_id=user_id, tender_id=tender_id
            )
        )
