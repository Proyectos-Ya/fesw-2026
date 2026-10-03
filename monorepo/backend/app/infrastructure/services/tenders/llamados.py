"""Llamado vigente y cierre de cada llamado, tal como los entrega Mercado Público.

Forma verificada en el listado real del 2026-09-28
(`tests/fixtures/mp_listado_cambios.json`):

    convocatoria: {"estado_convocatoria": 2, "descripcion": "Segundo llamado"}
    fechas: {"fecha_cierre": "2026-09-27 17:28",
             "fecha_cierre_primer_llamado": "2026-09-26T17:10:00Z",
             "fecha_cierre_segundo_llamado": "2026-09-27T17:28:48.093Z", ...}

Lo usan el listado (cron de estados) y el detalle (ingesta): si cada ruta leyera
distinto, una sobrescribiría a la otra en cada pasada. Que el detalle traiga
estos campos no está verificado (plan 233, fase 0): si no vienen, todo queda en
None y nadie borra lo que escribió el listado.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.shared.datetime_utils import leer_fecha_mp

LLAMADOS_VALIDOS = frozenset({1, 2})


@dataclass(frozen=True)
class LlamadoMp:
    """Llamado vigente y cierres por llamado, en hora de Chile naive.

    Sin pasar a UTC porque los dos consumidores convierten distinto: el DTO de
    ingesta normaliza en su validador y el cambio de estado se arma ya en UTC.
    """

    numero: int | None
    cierre_primer_llamado: datetime | None
    cierre_segundo_llamado: datetime | None


def leer_llamado(item: dict[str, Any]) -> LlamadoMp:
    fechas = item.get("fechas")
    fechas = fechas if isinstance(fechas, dict) else {}
    return LlamadoMp(
        numero=_numero(item.get("convocatoria")),
        cierre_primer_llamado=_al_minuto(_leer(fechas.get("fecha_cierre_primer_llamado"))),
        cierre_segundo_llamado=_al_minuto(_leer(fechas.get("fecha_cierre_segundo_llamado"))),
    )


def _numero(convocatoria: object) -> int | None:
    """1 o 2; cualquier otra cosa es None. Ante la duda no se afirma un llamado."""
    if not isinstance(convocatoria, dict):
        return None
    numero = convocatoria.get("estado_convocatoria")
    # `bool` es subclase de `int`: sin esto, `True` pasaría por primer llamado.
    if isinstance(numero, bool) or not isinstance(numero, int):
        return None
    return numero if numero in LLAMADOS_VALIDOS else None


def _leer(valor: object) -> datetime | None:
    # `leer_fecha_mp` llama `.strip()`: con un número reventaría con AttributeError.
    return leer_fecha_mp(valor) if isinstance(valor, str) else None


def _al_minuto(fecha: datetime | None) -> datetime | None:
    """Sin segundos ni milésimas.

    `fecha_cierre` llega al minuto, pero `fecha_cierre_segundo_llamado` trae
    segundos ("…17:28:48.093Z"). En un segundo llamado la API dice que son el
    mismo cierre; sin truncar diferirían en 48 s, y el hito y el contraste de
    fechas de anexos (decisión 4) quedarían corridos. Truncar y no redondear:
    17:28:48 es 17:28, igual que `fecha_cierre`.
    """
    return fecha.replace(second=0, microsecond=0) if fecha else None
