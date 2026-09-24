import re
from dataclasses import dataclass
from datetime import date, datetime, time

from app.domain.errors.milestone_errors import InvalidMilestoneDate
from app.shared.datetime_utils import to_utc_naive

# `date.fromisoformat` acepta también el formato básico ("20261020"); la IA
# debe entregar exactamente YYYY-MM-DD, así que el formato se exige aparte.
_FECHA_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
_HORA_ISO = re.compile(r"([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?")
_ANIO_MINIMO = 2000
_ANIO_MAXIMO = 2100


@dataclass(frozen=True)
class NormalizedMilestoneDate:
    due_at: datetime
    has_time: bool


def normalize_milestone_date(fecha: str, hora: str | None) -> NormalizedMilestoneDate:
    """Convierte fecha y hora locales de Chile en UTC naive.

    Sin hora, el hito queda a medianoche de Chile y marcado con `has_time=False`
    para que el usuario confirme una hora antes de sincronizarlo.
    """
    dia = _parse_fecha(fecha)
    hora_limpia = (hora or "").strip()
    if not hora_limpia:
        return NormalizedMilestoneDate(due_at=_a_utc(dia, time(0, 0)), has_time=False)
    return NormalizedMilestoneDate(due_at=_a_utc(dia, _parse_hora(hora_limpia)), has_time=True)


def _parse_fecha(fecha: str) -> date:
    if not _FECHA_ISO.fullmatch(fecha):
        raise InvalidMilestoneDate(f"La fecha '{fecha}' no tiene formato YYYY-MM-DD.")
    try:
        dia = date.fromisoformat(fecha)
    except ValueError:
        raise InvalidMilestoneDate(f"La fecha '{fecha}' no existe en el calendario.") from None
    if not _ANIO_MINIMO <= dia.year <= _ANIO_MAXIMO:
        raise InvalidMilestoneDate(f"La fecha '{fecha}' está fuera del rango aceptado.")
    return dia


def _parse_hora(hora: str) -> time:
    if not _HORA_ISO.fullmatch(hora):
        raise InvalidMilestoneDate(f"La hora '{hora}' no tiene formato HH:MM.")
    return time.fromisoformat(hora)


def _a_utc(dia: date, hora: time) -> datetime:
    utc = to_utc_naive(datetime.combine(dia, hora))
    assert utc is not None
    return utc
