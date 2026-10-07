"""Fusión de rankings mediante Reciprocal Rank Fusion (RRF) (Plan 256, Fase 1).

Permite combinar múltiples listas de candidatos (denso, sparse, MaxSim) sin requerir
normalización de escalas o calibración de pesos ad-hoc.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class FusedRankItem:
    """Ítem resultante de la fusión con su score RRF acumulado."""

    item_id: UUID
    score: float


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[UUID]],
    k: int = 60,
) -> list[FusedRankItem]:
    """Combina múltiples listas ordenadas de IDs usando RRF.

    Para cada lista, la posición r (0-based) aporta:
        1.0 / (k + r + 1)

    Args:
        rankings: Secuencia de listas ordenadas de IDs (de mejor a peor).
        k: Constante de suavizado RRF (por defecto 60).

    Returns:
        Lista ordenada de FusedRankItem de mayor a menor score.
    """
    scores: dict[UUID, float] = {}

    for ranking in rankings:
        for rank, item_id in enumerate(ranking):
            contribution = 1.0 / (k + rank + 1)
            scores[item_id] = scores.get(item_id, 0.0) + contribution

    sorted_items = sorted(
        scores.items(),
        key=lambda pair: pair[1],
        reverse=True,
    )

    return [FusedRankItem(item_id=uid, score=score) for uid, score in sorted_items]
