"""Caso de uso para el cálculo de matching enriquecido en sombra (Plan 233, Decisión 9)."""

from uuid import UUID

from app.application.repositories.matching_shadow_repository import (
    IMatchingShadowRepository,
)
from app.application.services.compatibility_scorer import CompatibilityScorer
from app.config import Settings
from app.domain.entities.matching_shadow import MatchingShadowScore, ShadowVariant
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender
from app.domain.entities.tender_digest import TenderDigest


class ComputeShadowScoreUseCase:
    """Calcula y persiste puntuaciones en sombra sin afectar los resultados visibles."""

    def __init__(
        self,
        scorer: CompatibilityScorer,
        shadow_repo: IMatchingShadowRepository,
        settings: Settings,
    ) -> None:
        self.scorer = scorer
        self.shadow_repo = shadow_repo
        self.settings = settings

    async def execute(
        self,
        supplier: Supplier,
        tender: Tender,
        digest: TenderDigest | None = None,
        ranking_id: UUID | None = None,
        variant: ShadowVariant = "att-text-v1",
    ) -> MatchingShadowScore | None:
        # 1. Kill-switch / Feature Flag: si está apagado, no se escribe nada
        if not self.settings.matching_shadow_enabled:
            return None

        # 2. Señales baseline (lo que vio o vería el usuario en producción)
        baseline_signals = await self.scorer.signals(supplier, tender)
        if not baseline_signals:
            return None

        # 3. Señales en sombra (enriquecidas con anexos)
        shadow_signals = await self.scorer.signals(
            supplier, tender, digest=digest, variant=variant
        )
        if not shadow_signals:
            return None

        # 4. Construir y persistir registro de sombra
        shadow_record = MatchingShadowScore(
            ranking_id=ranking_id,
            supplier_id=supplier.id,
            tender_id=tender.id,
            variant=variant,
            baseline_score=baseline_signals.final_score,
            shadow_score=shadow_signals.final_score,
            reranker_score=shadow_signals.reranker_score,
            best_match=shadow_signals.best_match,
            coverage=shadow_signals.coverage,
            model_version=self.scorer.model_version,
        )

        await self.shadow_repo.save_shadow_scores([shadow_record])
        return shadow_record
