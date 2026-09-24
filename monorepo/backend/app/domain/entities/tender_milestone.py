import math
from datetime import UTC, datetime, time, timedelta
from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints

from app.shared.datetime_utils import CHILE_TZ, UtcDateTime, to_utc_naive, utc_now_naive

_UN_DIA = timedelta(days=1)
_DIAS_CRITICO = 3
_DIAS_PROXIMO = 7


class MilestoneKind(StrEnum):
    PUBLICACION = "publicacion"
    CONSULTAS = "consultas"
    RESPUESTAS = "respuestas"
    VISITA_TECNICA = "visita_tecnica"
    CIERRE_POSTULACION = "cierre_postulacion"
    APERTURA = "apertura"
    ADJUDICACION = "adjudicacion"
    ENTREGA = "entrega"
    FIRMA_CONTRATO = "firma_contrato"
    OTRO = "otro"


class MilestoneSource(StrEnum):
    MERCADO_PUBLICO = "mercado_publico"
    IA_DOCUMENTO = "ia_documento"


class MilestoneUrgency(StrEnum):
    VENCIDO = "vencido"
    CRITICO = "critico"
    PROXIMO = "proximo"
    NORMAL = "normal"


def _recortar(maximo: int):
    def recortar(valor: object) -> object:
        if isinstance(valor, str):
            return valor.strip()[:maximo]
        return valor

    return BeforeValidator(recortar)


class TenderMilestone(BaseModel):
    """Hito con fecha de una licitación, visto por un usuario."""

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    tender_id: UUID
    kind: MilestoneKind
    title: Annotated[str, _recortar(200), StringConstraints(min_length=1)]
    description: Annotated[str | None, _recortar(2000)] = None
    source: MilestoneSource
    source_document_id: UUID | None = None
    source_excerpt: Annotated[str | None, _recortar(1000)] = None
    due_at: UtcDateTime
    has_time: bool
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)
    updated_at: UtcDateTime = Field(default_factory=utc_now_naive)

    def urgencia(self, now: datetime) -> MilestoneUrgency:
        """Mismos umbrales que `daysUntilClosing` del frontend."""
        restante = self.due_at - now
        if restante < timedelta(0):
            return MilestoneUrgency.VENCIDO
        dias = math.ceil(restante / _UN_DIA)
        if dias <= _DIAS_CRITICO:
            return MilestoneUrgency.CRITICO
        if dias <= _DIAS_PROXIMO:
            return MilestoneUrgency.PROXIMO
        return MilestoneUrgency.NORMAL

    def con_hora(self, hora: time) -> "TenderMilestone":
        """Copia del hito a la `hora` de Chile del mismo día local."""
        dia_local = self.due_at.replace(tzinfo=UTC).astimezone(CHILE_TZ).date()
        due_at = to_utc_naive(datetime.combine(dia_local, hora))
        return self.model_copy(update={"due_at": due_at, "has_time": True})
