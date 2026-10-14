"""Traduce un ítem del listado de Compra Ágil a un `CambioDeEstado`.

Forma verificada contra la API real el 2026-09-28
(`tests/fixtures/mp_listado_cambios.json`):

    estado: {"id_estado": 2, "codigo": "publicada", "glosa": "Publicada"}
    convocatoria: {"estado_convocatoria": 1, "descripcion": "Primer llamado"}
    fechas: {"fecha_cierre": "2026-09-29 13:30",
             "fecha_ultimo_cambio": "2026-09-28T13:20:00.353Z",
             "fecha_cierre_primer_llamado": "2026-09-29T13:30:00Z",
             "fecha_cierre_segundo_llamado": "2026-09-30T13:40:00.107Z", ...}

    documentos: [{"id": 1931002, "nombre": "Anexo 3 ....xlsx"}, ...]

`documentos` es la lista oficial de anexos y puede ser `[]` (sin anexos). Si no
viene o no se puede leer entera, queda en `None` y no invalida el cambio de
estado: lo único que pasa es que esa corrida no toca la lista guardada.

`fecha_cierre` sigue al llamado vigente (en un segundo llamado coincide con
`fecha_cierre_segundo_llamado`), así que una ampliación de plazo se ve acá.
`closing_at` conserva ese significado: `convocatoria` y los dos
`fecha_cierre_*_llamado` solo lo desglosan (plan 233, decisión 3). Tampoco son
imprescindibles: sin ellos, o ilegibles, el cambio de estado sirve igual y
esos campos quedan en `None` (ver `llamados.py`).
"""

from typing import Any

from app.domain.models.cambio_estado import CambioDeEstado
from app.infrastructure.services.tenders.documentos_mp import documentos_desde_payload
from app.infrastructure.services.tenders.llamados import leer_llamado
from app.shared.datetime_utils import fecha_mp_a_utc, to_utc_naive


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

    lista = documentos_desde_payload(item)
    llamado = leer_llamado(item)
    return CambioDeEstado(
        code=str(code),
        status_id=status_id,
        status_code=status_code,
        closing_at=closing_at,
        changed_at=fecha_mp_a_utc(fechas.get("fecha_ultimo_cambio")),
        documentos=tuple(lista) if lista is not None else None,
        call_number=llamado.numero,
        first_call_closing_at=to_utc_naive(llamado.cierre_primer_llamado),
        second_call_closing_at=to_utc_naive(llamado.cierre_segundo_llamado),
    )
