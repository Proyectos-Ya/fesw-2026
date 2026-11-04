"""Registra lo que hace el usuario con una licitación (plan 233, decisión 8)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.application.repositories.ranking_telemetry_repository import (
    IRankingTelemetryRepository,
)
from app.domain.entities.ranking_telemetry import (
    ATTRIBUTION_WINDOW,
    InteractionKind,
    InteractionSource,
    TenderInteraction,
)
from app.shared.datetime_utils import utc_now_naive


@dataclass(frozen=True)
class InteractionRecordResult:
    recorded: bool
    attributed: bool


class RecordTenderInteractionUseCase:
    """Guarda una interacción y la atribuye al ranking solo si se puede probar.

    Una interacción con `ranking_id` se atribuye únicamente si existe la
    impresión (ranking, licitación), es del mismo usuario, no trae otra empresa
    en el contexto y el ranking tiene menos de 7 días. Si no, se guarda sin
    ranking ni posición y no cuenta para el NDCG. La única que no se guarda es
    la impresión sin atribución: no aporta nada y no se podría deduplicar.
    """

    def __init__(
        self,
        repo: IRankingTelemetryRepository,
        now: Callable[[], datetime] = utc_now_naive,
    ) -> None:
        self.repo = repo
        self.now = now

    async def execute(
        self,
        *,
        user_id: UUID,
        supplier_id: UUID | None,
        tender_id: UUID,
        kind: InteractionKind,
        source: InteractionSource,
        ranking_id: UUID | None = None,
        position: int | None = None,
    ) -> InteractionRecordResult:
        now = self.now()
        attributed, stored_supplier = False, supplier_id
        if ranking_id is not None:
            impression = await self.repo.find_impression(ranking_id, tender_id)
            if (
                impression is not None
                and impression.user_id == user_id
                and (supplier_id is None or impression.supplier_id == supplier_id)
                and impression.created_at >= now - ATTRIBUTION_WINDOW
            ):
                attributed, stored_supplier = True, impression.supplier_id

        if kind == InteractionKind.IMPRESION and not attributed:
            # Sin ranking válido una impresión no aporta (ni NDCG ni top-10) y no
            # se podría deduplicar.
            return InteractionRecordResult(recorded=False, attributed=False)

        interaction = TenderInteraction(
            user_id=user_id,
            supplier_id=stored_supplier,
            tender_id=tender_id,
            kind=kind,
            ranking_id=ranking_id if attributed else None,
            position=position if attributed else None,
            source=source,
            created_at=now,
        )
        recorded = await self.repo.save_interaction(interaction)
        return InteractionRecordResult(recorded=recorded, attributed=attributed)
