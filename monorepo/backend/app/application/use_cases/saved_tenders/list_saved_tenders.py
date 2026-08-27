from uuid import UUID

from app.application.repositories.matching_result_repository import (
    IMatchingResultRepository,
)
from app.application.repositories.saved_tender_repository import (
    ISavedTenderRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.domain.entities.matching_result import MatchingResult


class ListSavedTendersUseCase:
    """Lista las licitaciones guardadas por el usuario con su score de matching real."""

    def __init__(
        self,
        saved_tender_repo: ISavedTenderRepository,
        tender_repo: ITenderRepository,
        supplier_repo: ISupplierRepository | None = None,
        matching_result_repo: IMatchingResultRepository | None = None,
    ):
        self.saved_tender_repo = saved_tender_repo
        self.tender_repo = tender_repo
        self.supplier_repo = supplier_repo
        self.matching_result_repo = matching_result_repo

    async def execute(self, user_id: UUID) -> list[MatchingResult]:
        saved = await self.saved_tender_repo.get_by_user_id(user_id)
        if not saved:
            return []

        saved_at_by_tender = {s.tender_id: s.saved_at for s in saved}
        saved_tender_ids = list(saved_at_by_tender.keys())

        # 1. Obtener las licitaciones
        tenders = await self.tender_repo.get_tenders(
            TenderFilters(ids=saved_tender_ids)
        )
        tender_by_id = {t.id: t for t in tenders}

        # 2. Obtener el proveedor de este usuario
        supplier = (
            await self.supplier_repo.get_by_user_id(user_id)
            if self.supplier_repo
            else None
        )

        # 3. Obtener los scores de matching calculados para la empresa
        match_by_tender_id: dict[UUID, MatchingResult] = {}
        if supplier and self.matching_result_repo:
            supplier_matches = await self.matching_result_repo.get_by_supplier_id(
                supplier.id
            )
            match_by_tender_id = {m.tender_id: m for m in supplier_matches}


        # 4. Construir y ordenar la lista final
        results: list[MatchingResult] = []
        for s in sorted(saved, key=lambda item: item.saved_at, reverse=True):
            tender = tender_by_id.get(s.tender_id)
            if not tender:
                continue

            match = match_by_tender_id.get(s.tender_id)
            if match:
                match.tender = tender
                results.append(match)
            else:
                # Fallback seguro
                results.append(
                    MatchingResult(
                        supplier_id=supplier.id if supplier else user_id,
                        tender_id=tender.id,
                        similarity_score=0.0,
                        final_score=0.0,
                        model_version="v1.0",
                        tender=tender,
                    )
                )

        return results