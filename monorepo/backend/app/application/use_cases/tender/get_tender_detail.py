from dataclasses import dataclass
from uuid import UUID

from app.application.repositories.matching_result_repository import (
    IMatchingResultRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.domain.entities.tender import Tender
from app.domain.errors.tender_errors import TenderNotFound
from app.shared.constants import ACTIVE_TENDER_STATUSES
from app.shared.datetime_utils import utc_now_naive


@dataclass
class TenderDetail:
    """Ficha de una licitación, esté abierta o cerrada."""

    tender: Tender
    # Score cacheado del proveedor para esta licitación, si alguna vez se
    # calculó. `None` significa "no lo sabemos", no "cero".
    final_score: float | None
    is_closed: bool


class GetTenderDetailUseCase:
    """Devuelve una licitación por id, sin filtrar por fecha de cierre.

    Existe precisamente porque `RankTendersUseCase` descarta las cerradas: una
    alerta enviada hace días puede apuntar a una licitación que ya cerró, y el
    usuario debe ver que cerró en vez de un "no encontrada" (HdU 08).
    """

    def __init__(
        self,
        tender_repo: ITenderRepository,
        supplier_repo: ISupplierRepository,
        matching_result_repo: IMatchingResultRepository,
    ) -> None:
        self.tender_repo = tender_repo
        self.supplier_repo = supplier_repo
        self.matching_result_repo = matching_result_repo

    async def execute(self, user_id: UUID, tender_id: UUID) -> TenderDetail:
        tenders = await self.tender_repo.get_tenders(TenderFilters(ids=[tender_id]))
        if not tenders:
            raise TenderNotFound(tender_id)
        tender = tenders[0]

        final_score: float | None = None
        supplier = await self.supplier_repo.get_by_user_id(user_id)
        if supplier is not None:
            match = await self.matching_result_repo.get_by_proveedor_and_licitacion(
                supplier.id, tender_id
            )
            if match is not None:
                final_score = match.final_score

        ahora = utc_now_naive()
        cerrada = (
            tender.closing_at <= ahora
            or tender.status_code not in ACTIVE_TENDER_STATUSES
        )
        return TenderDetail(tender=tender, final_score=final_score, is_closed=cerrada)
