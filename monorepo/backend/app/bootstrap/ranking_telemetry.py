"""Providers de la telemetría del ranking (plan 233, decisión 8)."""

import logging
from datetime import datetime
from uuid import UUID

from app.application.use_cases.ranking_telemetry.log_ranking_impressions import (
    LogRankingImpressionsUseCase,
    RankingImpressionLogger,
)
from app.application.use_cases.ranking_telemetry.record_tender_interaction import (
    RecordTenderInteractionUseCase,
)
from app.bootstrap.repositories import RankingTelemetryRepoDep
from app.domain.entities.matching_result import MatchingResult
from app.infrastructure.db import async_session_maker
from app.infrastructure.repositories.ranking_telemetry_repository import (
    SqlRankingTelemetryRepository,
)

logger = logging.getLogger(__name__)


async def registrar_impresiones_de_ranking(
    ranking_id: UUID,
    user_id: UUID,
    results: list[MatchingResult],
    served_at: datetime,
) -> None:
    """Escribe las posiciones servidas de un ranking.

    Corre como `BackgroundTask`, después de responder: abre su propia sesión (la
    de la petición ya puede estar cerrada) y nunca lanza, porque un fallo de
    telemetría no puede convertirse en un error para el usuario.
    """
    try:
        async with async_session_maker() as session:
            await LogRankingImpressionsUseCase(
                SqlRankingTelemetryRepository(session)
            ).execute(
                ranking_id=ranking_id,
                user_id=user_id,
                results=results,
                served_at=served_at,
            )
    except Exception as exc:
        # Sin `user_id` en el log: es un dato personal que no hace falta acá.
        logger.warning("No se pudo registrar el ranking %s: %s", ranking_id, exc)


def get_ranking_impression_logger() -> RankingImpressionLogger:
    return registrar_impresiones_de_ranking


def get_record_tender_interaction_use_case(
    repo: RankingTelemetryRepoDep,
) -> RecordTenderInteractionUseCase:
    return RecordTenderInteractionUseCase(repo=repo)
