"""Cálculo de tope diario y reanudación para Gemini (plan 233, decisión 4)."""

from datetime import date, datetime

from app.shared.datetime_utils import chile_date, chile_day_bounds_utc


def dia_del_tope(ahora_utc: datetime) -> date:
    """El tope cuenta por día de Chile: Railway corre en UTC y el equipo mira el gasto en hora local."""
    return chile_date(ahora_utc)


def reanudar_tope_en(ahora_utc: datetime) -> datetime:
    """Inicio del día siguiente de Chile, en UTC naive.

    No es `ahora + 24 h`: un día de cambio de hora dura 23 o 25 h, y ese cálculo
    soltaría la cola una hora antes o después de la medianoche.
    """
    return chile_day_bounds_utc(chile_date(ahora_utc))[1]
