"""Guarda las posiciones que sirvió `/tenders/recommended` (plan 233, decisión 8)."""

from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime
from uuid import UUID

from app.application.repositories.ranking_telemetry_repository import (
    IRankingTelemetryRepository,
)
from app.domain.entities.matching_result import MatchingResult
from app.domain.entities.ranking_telemetry import RankingImpression

# Firma del registrador que se encola como tarea en segundo plano:
# (ranking_id, user_id, resultados servidos, instante en que se sirvieron).
RankingImpressionLogger = Callable[
    [UUID, UUID, list[MatchingResult], datetime], Awaitable[None]
]


class LogRankingImpressionsUseCase:
    """Guarda las posiciones que sirvió /tenders/recommended, en el orden servido."""

    def __init__(self, repo: IRankingTelemetryRepository) -> None:
        self.repo = repo

    async def execute(
        self,
        *,
        ranking_id: UUID,
        user_id: UUID,
        results: Sequence[MatchingResult],
        served_at: datetime,
    ) -> int:
        """Devuelve cuántas posiciones guardó (0 si la lista venía vacía)."""
        if not results:
            return 0
        impressions = [
            RankingImpression(
                ranking_id=ranking_id,
                supplier_id=result.supplier_id,
                user_id=user_id,
                tender_id=result.tender_id,
                position=position,
                score=result.final_score,
                model_version=result.model_version,
                created_at=served_at,
            )
            for position, result in enumerate(results, start=1)
        ]
        await self.repo.save_impressions(impressions)
        return len(impressions)
