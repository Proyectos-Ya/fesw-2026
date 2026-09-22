from uuid import UUID

from app.application.repositories.matching_result_repository import (
    IMatchingResultRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.services.compatibility_scorer import CompatibilityScorer
from app.domain.entities.matching_result import MatchingResult
from app.domain.errors.supplier_errors import SupplierNotFoundForUser
from app.domain.errors.tender_errors import TenderClosedForScoring, TenderNotFound


class ScoreTenderOnDemandUseCase:
    """Calcula la compatibilidad de una licitación que el usuario eligió.

    El ranking solo puntúa su top-N, así que todo lo que llega del buscador, de
    las guardadas o de un enlace queda sin porcentaje. Este caso de uso cubre
    ese hueco, pero nunca por su cuenta: se ejecuta cuando alguien lo pide, y
    deja el resultado guardado para que la siguiente visita no vuelva a pagar la
    inferencia ni vea un número distinto.
    """

    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        tender_repo: ITenderRepository,
        matching_result_repo: IMatchingResultRepository,
        scorer: CompatibilityScorer,
    ) -> None:
        self.supplier_repo = supplier_repo
        self.tender_repo = tender_repo
        self.matching_result_repo = matching_result_repo
        self.scorer = scorer

    async def execute(self, user_id: UUID, tender_id: UUID) -> MatchingResult:
        supplier = await self.supplier_repo.get_by_user_id(user_id)
        if not supplier:
            raise SupplierNotFoundForUser(user_id)

        tenders = await self.tender_repo.get_tenders(TenderFilters(ids=[tender_id]))
        if not tenders:
            raise TenderNotFound(tender_id)
        tender = tenders[0]

        if tender.esta_cerrada():
            raise TenderClosedForScoring(tender_id)

        fila = await self.matching_result_repo.get_by_proveedor_and_licitacion(
            proveedor_id=supplier.id, licitacion_id=tender_id
        )
        if fila is not None and fila.source == "ranking":
            # Es una recomendación: su puntaje lo mantiene al día el pipeline.
            # Recalcularlo acá la convertiría en un cálculo a pedido y la
            # sacaría del dashboard hasta el siguiente ranking.
            return fila

        return await self.scorer.score_and_persist(supplier, tender)
