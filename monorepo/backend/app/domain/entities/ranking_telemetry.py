"""Telemetría del ranking: qué se mostró y qué hizo el usuario con eso (plan 233, decisión 8).

Alimenta dos cosas que hoy solo se miden offline: el NDCG@10 en producción por
versión del modelo y una prioridad de anexos que nadie consume todavía (en sombra).
"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.shared.datetime_utils import UtcDateTime, utc_now_naive


class InteractionKind(StrEnum):
    IMPRESION = "impresion"
    DETALLE = "detalle"
    GUARDAR = "guardar"
    FICHA_MP = "ficha_mp"
    ANEXO = "anexo"  # lo emitirá el panel de anexos (decisión 2); hoy nadie lo manda
    ASISTENTE = "asistente"
    ANALISIS = "analisis"
    COTIZACION = "cotizacion"


# Ganancia de relevancia (plan 233, decisión 8). La impresión vale 0: ver una tarjeta
# dice que estuvo en pantalla, no que sirva. La relevancia de una licitación dentro de
# un ranking es la MAYOR ganancia entre sus interacciones atribuidas.
INTERACTION_GAINS: dict[InteractionKind, int] = {
    InteractionKind.IMPRESION: 0,
    InteractionKind.DETALLE: 1,
    InteractionKind.GUARDAR: 2,
    InteractionKind.FICHA_MP: 2,
    InteractionKind.ANEXO: 2,
    InteractionKind.ASISTENTE: 2,
    InteractionKind.ANALISIS: 3,
    InteractionKind.COTIZACION: 3,
}

# Superficie donde ocurrió. El frontend manda hoy las tres primeras; las otras se
# aceptan desde ya para no exigir un despliegue del backend cuando se sumen.
InteractionSource = Literal[
    "inicio", "matches", "detalle", "busqueda", "guardadas", "notificacion"
]

# Una interacción se atribuye a un ranking servido hace a lo más 7 días. Por eso el
# NDCG de un día se recalcula durante los 7 siguientes.
ATTRIBUTION_WINDOW = timedelta(days=7)
# Impresiones, interacciones y snapshots crudos: 90 días. Después quedan solo los agregados.
RAW_RETENTION = timedelta(days=90)
# Ventana de señales de la prioridad en sombra.
PRIORITY_WINDOW = timedelta(days=7)


class RankingImpression(BaseModel):
    """Una posición servida por `/tenders/recommended`, antes de los filtros del frontend."""

    id: UUID = Field(default_factory=uuid4)
    ranking_id: UUID
    supplier_id: UUID
    user_id: UUID
    tender_id: UUID
    position: int = Field(ge=1)
    score: float | None = None
    model_version: str
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)


class TenderInteraction(BaseModel):
    """Algo que el usuario hizo con una licitación. `ranking_id` solo si se pudo atribuir."""

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    supplier_id: UUID | None = None
    tender_id: UUID
    kind: InteractionKind
    ranking_id: UUID | None = None
    position: int | None = None  # la MOSTRADA (tras filtros y paginación), no la servida
    source: InteractionSource
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)


class RankingMetricDaily(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    day: date  # día de Chile en que se sirvieron los rankings
    model_version: str
    ndcg_at_10: float  # promedio de los rankings con al menos una ganancia > 0
    ci_low: float
    ci_high: float
    rankings_evaluated: int
    rankings_served: int  # incluye los que no tuvieron interacciones
    computed_at: UtcDateTime = Field(default_factory=utc_now_naive)


class AttachmentPriorityShadow(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    tender_id: UUID
    computed_at: UtcDateTime
    priority: float
    components: dict[str, float | int | bool]


@dataclass(frozen=True)
class PurgeCounts:
    impressions: int = 0
    interactions: int = 0
    priority_snapshots: int = 0
