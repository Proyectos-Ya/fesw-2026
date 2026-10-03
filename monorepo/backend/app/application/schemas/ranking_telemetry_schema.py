"""Esquemas HTTP de la telemetría del ranking (plan 233, decisión 8)."""

from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.entities.matching_result import MatchingResult
from app.domain.entities.ranking_telemetry import InteractionKind, InteractionSource


class RecommendedTenderResponse(MatchingResult):
    """Un match del ranking más la lista a la que pertenece.

    Campos extra y no un envoltorio: el frontend anterior sigue leyendo una lista,
    y Railway y Vercel despliegan por separado.
    """

    ranking_id: UUID | None = Field(
        default=None,
        description="Identifica esta respuesta del ranking. Nulo con track=false.",
    )
    ranking_position: int = Field(
        description="Posición servida, 1..N, antes de los filtros del frontend."
    )


class TenderInteractionRequest(BaseModel):
    kind: InteractionKind
    source: InteractionSource
    ranking_id: UUID | None = None
    position: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Posición MOSTRADA. Se ignora sin ranking_id.",
    )


class TenderInteractionResponse(BaseModel):
    recorded: bool = Field(
        description="False si ya estaba (misma lista, licitación y tipo) o si era "
        "una impresión sin ranking válido."
    )
    attributed: bool = Field(description="True si cuenta para el NDCG.")
