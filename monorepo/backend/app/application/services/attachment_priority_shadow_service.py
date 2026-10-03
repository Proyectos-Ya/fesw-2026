"""Prioridad de anexos en sombra (plan 233, decisión 8).

Cuánto convendría procesar primero los anexos de una licitación. Se calcula y se
guarda para poder compararla con lo que pasó de verdad, pero **nadie la consume**:
la cola de la extensión no la usa hasta validarla, y un test de arquitectura
(`test_prioridad_sombra_sin_consumo.py`) lo asegura. Usarla exige un PR y un ADR
aparte.

Puro: sin base ni red.
"""

import math

URGENCY_MIN_HOURS = 2.0
URGENCY_PEAK_START_HOURS = 24.0
URGENCY_PEAK_END_HOURS = 72.0
URGENCY_ZERO_HOURS = 168.0
# Una impresión cuenta para la prioridad solo si la tarjeta se mostró entre las
# primeras diez posiciones.
TOP_POSITIONS = 10


class AttachmentPriorityShadowService:
    @staticmethod
    def closing_urgency(hours_to_close: float) -> float:
        """Trapecio: 0 a las 2 h, sube a 1 a las 24 h, 1 hasta las 72 h, baja a 0 a los 7 días.

        El pico de 1 a 3 días es cuando se arma la oferta; a menos de un día ya
        casi no hay tiempo de usar el anexo, y a más de una semana no apura.
        """
        h = hours_to_close
        if h <= URGENCY_MIN_HOURS or h >= URGENCY_ZERO_HOURS:
            return 0.0
        if h < URGENCY_PEAK_START_HOURS:
            return (h - URGENCY_MIN_HOURS) / (
                URGENCY_PEAK_START_HOURS - URGENCY_MIN_HOURS
            )
        if h <= URGENCY_PEAK_END_HOURS:
            return 1.0
        return (URGENCY_ZERO_HOURS - h) / (URGENCY_ZERO_HOURS - URGENCY_PEAK_END_HOURS)

    def priority(
        self,
        *,
        top10_impressions: int,
        interactions: int,
        manual_upload: bool,
        hours_to_close: float,
    ) -> tuple[float, dict[str, float | int | bool]]:
        """`3·log1p(impresiones top-10) + 2·log1p(interacciones) + 2·subida + urgencia`."""
        urgency = self.closing_urgency(hours_to_close)
        value = (
            3 * math.log1p(top10_impressions)
            + 2 * math.log1p(interactions)
            + (2.0 if manual_upload else 0.0)
            + urgency
        )
        return value, {
            "impresiones_top10_7d": top10_impressions,
            "interacciones_7d": interactions,
            "subida_manual": manual_upload,
            "horas_al_cierre": round(hours_to_close, 2),
            "urgencia_cierre": round(urgency, 4),
        }
