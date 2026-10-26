"""Replay y evaluación comparativa offline/online de rankings con scores en sombra (Plan 233, Decisión 9)."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from app.application.services.ranking_metrics_service import RankingMetricsService
from app.domain.entities.ranking_telemetry import (
    INTERACTION_GAINS,
    RankingImpression,
    TenderInteraction,
)


@dataclass(frozen=True)
class ReplayComparisonResult:
    """Resultado comparativo de replay entre el ranking servido y la variante en sombra."""

    baseline_ndcg_at_10: float
    shadow_ndcg_at_10: float
    delta_ndcg: float
    rankings_evaluated: int


class ReplayShadowRankingUseCase:
    """Reordena las listas servidas según las puntuaciones en sombra y compara el NDCG@10."""

    def __init__(self, metrics_service: RankingMetricsService | None = None) -> None:
        self.metrics_service = metrics_service or RankingMetricsService()

    def execute(
        self,
        impressions: Sequence[RankingImpression],
        interactions: Sequence[TenderInteraction],
        shadow_scores: dict[tuple[UUID, UUID], float],
    ) -> ReplayComparisonResult:
        if not impressions:
            return ReplayComparisonResult(
                baseline_ndcg_at_10=0.0,
                shadow_ndcg_at_10=0.0,
                delta_ndcg=0.0,
                rankings_evaluated=0,
            )

        # 1. Ganancia máxima atribuida por (ranking_id, tender_id)
        gain_by_key: dict[tuple[UUID, UUID], int] = {}
        for interaction in interactions:
            if interaction.ranking_id is None:
                continue
            key = (interaction.ranking_id, interaction.tender_id)
            gain = INTERACTION_GAINS[interaction.kind]
            if gain > gain_by_key.get(key, 0):
                gain_by_key[key] = gain

        # 2. Agrupar impresiones por ranking
        by_ranking: dict[UUID, list[RankingImpression]] = defaultdict(list)
        for impression in impressions:
            by_ranking[impression.ranking_id].append(impression)

        baseline_ndcgs: list[float] = []
        shadow_ndcgs: list[float] = []

        for ranking_id, rows in by_ranking.items():
            # Orden servido (baseline)
            baseline_sorted = sorted(rows, key=lambda r: r.position)
            baseline_relevances = [
                gain_by_key.get((ranking_id, r.tender_id), 0)
                for r in baseline_sorted
            ]
            b_ndcg = self.metrics_service.ndcg(baseline_relevances)

            # Reordenamiento según shadow_score (de mayor a menor)
            shadow_sorted = sorted(
                rows,
                key=lambda r: shadow_scores.get(
                    (ranking_id, r.tender_id), r.score or 0.0
                ),
                reverse=True,
            )
            shadow_relevances = [
                gain_by_key.get((ranking_id, r.tender_id), 0)
                for r in shadow_sorted
            ]
            s_ndcg = self.metrics_service.ndcg(shadow_relevances)

            # Solo se comparan rankings que tuvieron alguna interacción
            if b_ndcg is not None and s_ndcg is not None:
                baseline_ndcgs.append(b_ndcg)
                shadow_ndcgs.append(s_ndcg)

        count = len(baseline_ndcgs)
        if count == 0:
            return ReplayComparisonResult(
                baseline_ndcg_at_10=0.0,
                shadow_ndcg_at_10=0.0,
                delta_ndcg=0.0,
                rankings_evaluated=0,
            )

        avg_baseline = sum(baseline_ndcgs) / count
        avg_shadow = sum(shadow_ndcgs) / count
        delta = avg_shadow - avg_baseline

        return ReplayComparisonResult(
            baseline_ndcg_at_10=avg_baseline,
            shadow_ndcg_at_10=avg_shadow,
            delta_ndcg=delta,
            rankings_evaluated=count,
        )
