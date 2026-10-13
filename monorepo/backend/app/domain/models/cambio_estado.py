"""Lo que el cron de estados necesita saber de una licitación que cambió.

Sale del **listado** de Mercado Público, no del detalle: estado y fecha de
cierre vienen ahí, así que actualizarlos no cuesta una petición por licitación.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.models.tender_ingestion_dto import DocumentoOficialDTO


@dataclass(frozen=True)
class CambioDeEstado:
    """Estado, cierre y llamado de una licitación según el listado de cambios.

    Todas las fechas en UTC naive (invariante de persistencia).
    """

    code: str
    status_id: int
    status_code: str
    closing_at: datetime
    # `fecha_ultimo_cambio` de la API. Sirve para decidir si hay que volver a
    # bajar el detalle; puede faltar sin que el estado deje de ser útil.
    changed_at: datetime | None = None
    # Lista oficial de anexos del ítem del listado. Tupla porque el dataclass es
    # congelado. `None` = el ítem no la trae legible: no se toca la guardada.
    documentos: tuple[DocumentoOficialDTO, ...] | None = None
    # Llamado vigente (`convocatoria.estado_convocatoria`: 1 o 2) y el cierre de
    # cada llamado, en UTC naive y al minuto. No son imprescindibles: un ítem
    # sin ellos igual aplica estado y cierre. `closing_at` sigue al llamado
    # vigente; estos campos lo desglosan.
    call_number: int | None = None
    first_call_closing_at: datetime | None = None
    second_call_closing_at: datetime | None = None

    @property
    def trae_llamado(self) -> bool:
        return any(
            v is not None
            for v in (
                self.call_number,
                self.first_call_closing_at,
                self.second_call_closing_at,
            )
        )


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
    # Filas cuyo llamado o cierre por llamado cambió. No mueven `updated_at`.
    llamados_actualizados: int = 0
    # Dejaron de estar activas: su punto se borra del índice vectorial.
    sacadas_del_indice: int = 0
    # Volvieron a estar activas: no tienen punto, así que las reindexa el ingest.
    reabiertas: int = 0
    reencoladas: int = 0
