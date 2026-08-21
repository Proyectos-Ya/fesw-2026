from uuid import UUID

from app.application.repositories.saved_tender_repository import ISavedTenderRepository
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.domain.entities.tender import Tender


class ListSavedTendersUseCase:
    """Lista las licitaciones que el usuario autenticado marcó como de interés."""

    def __init__(
        self,
        saved_tender_repo: ISavedTenderRepository,
        tender_repo: ITenderRepository,
    ):
        self.saved_tender_repo = saved_tender_repo
        self.tender_repo = tender_repo

    async def execute(self, user_id: UUID) -> list[Tender]:
        saved = await self.saved_tender_repo.get_by_user_id(user_id)

        # Corte temprano obligatorio: get_tenders solo aplica el filtro cuando
        # `ids` tiene elementos, así que una lista vacía traería *todas* las
        # licitaciones de la base en vez de ninguna.
        if not saved:
            return []

        saved_at_by_tender = {s.tender_id: s.saved_at for s in saved}
        tenders = await self.tender_repo.get_tenders(
            TenderFilters(ids=list(saved_at_by_tender.keys()))
        )

        # La consulta SQL no garantiza orden: se ordena por fecha de guardado
        # descendente para que lo último marcado aparezca primero.
        return sorted(
            tenders,
            key=lambda tender: saved_at_by_tender[tender.id],
            reverse=True,
        )
