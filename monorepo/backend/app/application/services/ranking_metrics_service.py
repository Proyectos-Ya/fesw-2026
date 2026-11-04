"""NDCG@10 de los rankings que se sirvieron en producción (plan 233, decisión 8).

Puro: sin base ni red. Recibe las posiciones servidas y las interacciones ya
atribuidas, y devuelve el promedio por versión del modelo con su intervalo de
confianza por bootstrap.
"""

import math
import random
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from app.domain.entities.ranking_telemetry import (
    INTERACTION_GAINS,
    RankingImpression,
    TenderInteraction,
)

NDCG_K = 10
BOOTSTRAP_RESAMPLES = 1000
BOOTSTRAP_CONFIDENCE = 0.95


@dataclass(frozen=True)
class RankingEvaluation:
    ndcg_at_10: float
    ci_low: float
    ci_high: float
    rankings_evaluated: int
    rankings_served: int


class RankingMetricsService:
    """NDCG@10 de los rankings servidos en producción. Puro: sin base ni red."""

    def __init__(
        self,
        k: int = NDCG_K,
        resamples: int = BOOTSTRAP_RESAMPLES,
        confidence: float = BOOTSTRAP_CONFIDENCE,
        seed: int = 0,
    ) -> None:
        self.k = k
        self.resamples = resamples
        self.confidence = confidence
        self.seed = seed

    @staticmethod
    def dcg(relevances: Sequence[float]) -> float:
        # `i` parte en 1: la primera posición divide por log2(2) = 1.
        return sum(
            rel / math.log2(i + 1) for i, rel in enumerate(relevances, start=1)
        )

    def ndcg(self, relevances: Sequence[float]) -> float | None:
        """NDCG@k de un ranking, o `None` si ninguna licitación tuvo ganancia.

        Sin ganancia no hay NDCG: el ranking queda fuera del promedio en vez de
        contar como 0, porque que nadie haya interactuado no dice que el orden
        fuera malo.
        """
        ideal = self.dcg(sorted(relevances, reverse=True)[: self.k])
        if ideal == 0:
            return None
        return self.dcg(list(relevances)[: self.k]) / ideal

    @staticmethod
    def relevance_by_ranking(
        impressions: Sequence[RankingImpression],
        interactions: Sequence[TenderInteraction],
    ) -> dict[UUID, list[int]]:
        """Relevancia de cada posición servida, en el orden servido.

        La de una licitación dentro de un ranking es la MAYOR ganancia entre sus
        interacciones atribuidas a ese ranking. Las que no traen `ranking_id` no
        cuentan.
        """
        gain_by_key: dict[tuple[UUID, UUID], int] = {}
        for interaction in interactions:
            if interaction.ranking_id is None:
                continue
            key = (interaction.ranking_id, interaction.tender_id)
            gain = INTERACTION_GAINS[interaction.kind]
            if gain > gain_by_key.get(key, 0):
                gain_by_key[key] = gain

        # La base no garantiza el orden: se ordena por la posición servida.
        by_ranking: dict[UUID, list[RankingImpression]] = defaultdict(list)
        for impression in impressions:
            by_ranking[impression.ranking_id].append(impression)

        return {
            ranking_id: [
                gain_by_key.get((ranking_id, i.tender_id), 0)
                for i in sorted(rows, key=lambda row: row.position)
            ]
            for ranking_id, rows in by_ranking.items()
        }

    def bootstrap_ci(self, values: Sequence[float]) -> tuple[float, float]:
        """Intervalo de confianza de la media por percentil de remuestreos.

        Determinista: el generador es nuevo en cada llamada, así que los mismos
        valores dan siempre el mismo intervalo.
        """
        n = len(values)
        if n == 1:
            return values[0], values[0]
        rng = random.Random(self.seed)
        means = sorted(
            sum(rng.choices(values, k=n)) / n for _ in range(self.resamples)
        )
        tail = (1 - self.confidence) / 2
        low = means[int(tail * self.resamples)]
        high = means[int((1 - tail) * self.resamples) - 1]
        return low, high

    def evaluate(
        self,
        impressions: Sequence[RankingImpression],
        interactions: Sequence[TenderInteraction],
    ) -> RankingEvaluation | None:
        """Promedio del NDCG@k de los rankings con al menos una ganancia.

        `None` si ninguno la tuvo. Los rankings se recorren ordenados por id para
        que el bootstrap sea reproducible.
        """
        relevances = self.relevance_by_ranking(impressions, interactions)
        scores = [
            score
            for ranking_id in sorted(relevances)
            if (score := self.ndcg(relevances[ranking_id])) is not None
        ]
        if not scores:
            return None
        low, high = self.bootstrap_ci(scores)
        return RankingEvaluation(
            ndcg_at_10=sum(scores) / len(scores),
            ci_low=low,
            ci_high=high,
            rankings_evaluated=len(scores),
            rankings_served=len(relevances),
        )
