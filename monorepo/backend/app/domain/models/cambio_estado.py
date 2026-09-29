"""Lo que el cron de estados necesita saber de una licitación que cambió.

Sale del **listado** de Mercado Público, no del detalle: estado y fecha de
cierre vienen ahí, así que actualizarlos no cuesta una petición por licitación.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class CambioDeEstado:
    """Estado y cierre de una licitación según el listado de cambios.

    Todas las fechas en UTC naive (invariante de persistencia).
    """

    code: str
    status_id: int
    status_code: str
    closing_at: datetime
    # `fecha_ultimo_cambio` de la API. Sirve para decidir si hay que volver a
    # bajar el detalle; puede faltar sin que el estado deje de ser útil.
    changed_at: datetime | None = None


@dataclass(frozen=True)
class LicitacionConocida:
    """Lo mínimo de una licitación guardada para aplicarle un cambio.

    `last_change_at` es cuándo el ingest bajó su detalle por última vez, no la
    fecha de cambio de la API.
    """

    id: UUID
    code: str
    status_id: int
    last_change_at: datetime | None


@dataclass
class ResultadoSyncEstados:
    """Qué hizo una pasada del cron de estados."""

    conocidas: int = 0
    # Filas de `tender` que cambiaron de verdad (estado o cierre).
    actualizadas: int = 0
    # Dejaron de estar activas: su punto se borra del índice vectorial.
    sacadas_del_indice: int = 0
    # Volvieron a estar activas: no tienen punto, así que las reindexa el ingest.
    reabiertas: int = 0
    reencoladas: int = 0
