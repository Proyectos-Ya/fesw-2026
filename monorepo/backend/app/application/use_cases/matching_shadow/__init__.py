"""Módulo de casos de uso para matching en sombra (Plan 233, Decisión 9)."""

from app.application.use_cases.matching_shadow.compute_shadow_score import (
    ComputeShadowScoreUseCase,
)
from app.application.use_cases.matching_shadow.replay_shadow_ranking import (
    ReplayComparisonResult,
    ReplayShadowRankingUseCase,
)

__all__ = [
    "ComputeShadowScoreUseCase",
    "ReplayComparisonResult",
    "ReplayShadowRankingUseCase",
]
