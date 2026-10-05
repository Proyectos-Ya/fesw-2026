import math
from datetime import UTC, datetime, time, timedelta
from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints

from app.shared.datetime_utils import CHILE_TZ, UtcDateTime, to_utc_naive, utc_now_naive

_UN_DIA = timedelta(days=1)
_DIAS_CRITICO = 3
# El criterio 9 de la HU-16 pide destacar el hito cuando le quedan 5 días o menos.
_DIAS_PROXIMO = 5

# Anticipaciones que el usuario puede elegir para el recordatorio de un hito.
REMINDER_DAYS_OPTIONS = (1, 3, 7)


class MilestoneKind(StrEnum):
    PUBLICACION = "publicacion"
    CONSULTAS = "consultas"
    RESPUESTAS = "respuestas"
    VISITA_TECNICA = "visita_tecnica"
    CIERRE_POSTULACION = "cierre_postulacion"
    CIERRE_SEGUNDO_LLAMADO = "cierre_segundo_llamado"
    APERTURA = "apertura"
    ADJUDICACION = "adjudicacion"
    ENTREGA = "entrega"
    FIRMA_CONTRATO = "firma_contrato"
    OTRO = "otro"


# Hitos que salen solo de los datos de Mercado Público, nunca de un documento.
# La IA no los ofrece: si los extrajera, quedarían duplicados del oficial con
# otra clave (tipo, título) en `merge_milestones`.
OFFICIAL_ONLY_KINDS: frozenset[MilestoneKind] = frozenset(
    {MilestoneKind.CIERRE_SEGUNDO_LLAMADO}
)


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
    source_file_id: UUID | None = None
    source_excerpt: Annotated[str | None, _recortar(1000)] = None
    due_at: UtcDateTime
    has_time: bool
    # Días de anticipación del recordatorio. Nulo = el usuario no lo activó.
    reminder_days_before: int | None = Field(default=None, ge=1, le=365)
    reminder_sent_at: UtcDateTime | None = None
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)
    updated_at: UtcDateTime = Field(default_factory=utc_now_naive)

    def recordatorio_pendiente(self, now: datetime) -> bool:
        """Si toca avisar de este hito ahora (criterio 10).

        Solo dentro de la ventana que va desde la anticipación elegida hasta el
        vencimiento: un hito ya vencido no se recuerda, y `reminder_sent_at`
        impide repetirlo en la vuelta siguiente del loop.
        """
        if self.reminder_days_before is None or self.reminder_sent_at is not None:
            return False
        return self.due_at - timedelta(days=self.reminder_days_before) <= now < self.due_at

    def con_recordatorio_enviado(self, now: datetime) -> "TenderMilestone":
        return self.model_copy(update={"reminder_sent_at": now, "updated_at": now})

    def urgencia(self, now: datetime) -> MilestoneUrgency:
        """Vencido, crítico (3 días o menos) o próximo (5 días o menos, criterio 9)."""
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
