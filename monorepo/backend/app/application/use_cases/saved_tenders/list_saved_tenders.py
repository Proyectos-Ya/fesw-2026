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
    """Lista las licitaciones guardadas del workspace con su score real.

    HU-18: todos los miembros del workspace ven la misma lista, filtrada por
    `supplier_id`. El score usa el `MatchingResult` del `supplier_id` del
    workspace (que ya es el ID consultado); no hay más resolución necesaria.
    """

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

    async def execute(self, supplier_id: UUID) -> list[MatchingResult]:
        saved = await self.saved_tender_repo.get_by_supplier_id(supplier_id)
        if not saved:
            return []

        saved_at_by_tender = {s.tender_id: s.saved_at for s in saved}
        saved_tender_ids = list(saved_at_by_tender.keys())

        tenders = await self.tender_repo.get_tenders(
            TenderFilters(ids=saved_tender_ids)
        )
        tender_by_id = {t.id: t for t in tenders}

        # Scores de matching para el workspace. El supplier_id del workspace es
        # el que se consulta; no hay fallback a user_id porque las guardadas ya
        # viven a nivel de workspace.
        match_by_tender_id: dict[UUID, MatchingResult] = {}
        if self.matching_result_repo is not None:
            supplier_matches = await self.matching_result_repo.get_by_supplier_id(
                supplier_id
            )
            match_by_tender_id = {m.tender_id: m for m in supplier_matches}

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
                # Sin puntaje calculado todavía. Se devuelve en nulo: un 0.0
                # acá se leería como "incompatible", cuando lo cierto es que
                # nadie lo ha medido.
                results.append(
                    MatchingResult(
                        supplier_id=supplier_id,
                        tender_id=tender.id,
                        similarity_score=None,
                        final_score=None,
                        model_version="v1.0",
                        tender=tender,
                    )
                )

        return results
