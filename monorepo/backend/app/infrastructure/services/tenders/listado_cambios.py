"""Traduce un ítem del listado de Compra Ágil a un `CambioDeEstado`.

Forma verificada contra la API real el 2026-09-28
(`tests/fixtures/mp_listado_cambios.json`):

    estado: {"id_estado": 2, "codigo": "publicada", "glosa": "Publicada"}
    fechas: {"fecha_cierre": "2026-09-29 13:30",
             "fecha_ultimo_cambio": "2026-09-28T13:20:00.353Z", ...}

`fecha_cierre` sigue al llamado vigente (en un segundo llamado coincide con
`fecha_cierre_segundo_llamado`), así que una ampliación de plazo se ve acá.
"""

from typing import Any

from app.domain.models.cambio_estado import CambioDeEstado
from app.shared.datetime_utils import fecha_mp_a_utc


def cambio_desde_item(item: dict[str, Any]) -> CambioDeEstado | None:
    """El cambio de estado del ítem, o `None` si le falta algo imprescindible.

    Ante la duda no se escribe: sobrescribir el estado o el cierre con un valor
    inventado es peor que dejar el que había hasta la corrida siguiente.
    """
    code = item.get("codigo")
    estado = item.get("estado") or {}
    fechas = item.get("fechas") or {}
    if not code or not isinstance(estado, dict) or not isinstance(fechas, dict):
        return None

    status_id = estado.get("id_estado")
    status_code = str(estado.get("codigo") or "").strip().lower()
    closing_at = fecha_mp_a_utc(fechas.get("fecha_cierre"))
    if not isinstance(status_id, int) or not status_code or closing_at is None:
        return None

    return CambioDeEstado(
        code=str(code),
        status_id=status_id,
        status_code=status_code,
        closing_at=closing_at,
        changed_at=fecha_mp_a_utc(fechas.get("fecha_ultimo_cambio")),
    )
