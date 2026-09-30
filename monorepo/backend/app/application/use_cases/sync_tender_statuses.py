"""Aplica a las licitaciones guardadas el estado y el cierre del listado de cambios.

La ingesta nocturna solo descubre licitaciones nuevas: una ya procesada no se
vuelve a mirar. Sin esto, una desierta o cancelada seguía figurando publicada
hasta su cierre original, y una con el plazo ampliado se cerraba con la fecha
vieja mientras todavía se podía postular.

Se escribe desde el **listado**, sin pedir el detalle: estado y cierre vienen
ahí. Lo que solo trae el detalle (descripción, partidas) no se puede saber desde
el listado; para eso se **reencola** la licitación y el ingest decide, con
`_actualizar`, si cambió el texto.
"""

from datetime import datetime

from app.application.repositories.tender_status_sync_repository import (
    ITenderStatusSyncRepository,
)
from app.application.repositories.tender_vector_repository import (
    ITenderVectorRepository,
)
from app.application.services.tender_ingestion_queue import ITenderIngestionQueue
from app.domain.models.cambio_estado import (
    CambioDeEstado,
    LicitacionConocida,
    ResultadoSyncEstados,
)
from app.shared.constants import ACTIVE_TENDER_STATUSES, TENDER_STATUS_CODE_BY_ID
from app.shared.datetime_utils import to_utc_epoch


def _esta_activa(status_id: int) -> bool:
    """Mismo criterio que la ingesta: un id sin mapeo cuenta como no activo."""
    return TENDER_STATUS_CODE_BY_ID.get(status_id) in ACTIVE_TENDER_STATUSES


def _mas_reciente_por_codigo(cambios: list[CambioDeEstado]) -> list[CambioDeEstado]:
    """Un cambio por código: el de `changed_at` más reciente.

    El listado pagina mientras la API sigue cambiando, así que un código puede
    aparecer dos veces. Sin fecha cuenta como el más viejo.
    """
    por_codigo: dict[str, CambioDeEstado] = {}
    for cambio in cambios:
        actual = por_codigo.get(cambio.code)
        if actual is None or _momento(cambio) > _momento(actual):
            por_codigo[cambio.code] = cambio
    return list(por_codigo.values())


def _momento(cambio: CambioDeEstado) -> datetime:
    return cambio.changed_at or datetime.min


def _cambio_posterior_a_la_bajada(
    cambio: CambioDeEstado, conocida: LicitacionConocida
) -> bool:
    if cambio.changed_at is None:
        return False
    return (
        conocida.last_change_at is None or cambio.changed_at > conocida.last_change_at
    )


class SyncTenderStatusesUseCase:
    def __init__(
        self,
        repository: ITenderStatusSyncRepository,
        tender_vector_repo: ITenderVectorRepository,
        cola: ITenderIngestionQueue,
    ) -> None:
        self.repo = repository
        self.tender_vector_repo = tender_vector_repo
        self.cola = cola

    async def execute(self, cambios: list[CambioDeEstado]) -> ResultadoSyncEstados:
        resultado = ResultadoSyncEstados()
        cambios = _mas_reciente_por_codigo(cambios)
        if not cambios:
            return resultado

        conocidas = await self.repo.get_known_by_codes([c.code for c in cambios])
        resultado.conocidas = len(conocidas)

        a_borrar = []
        payloads = {}
        a_sobrescribir: list[CambioDeEstado] = []
        a_reencolar: list[str] = []

        for cambio in cambios:
            conocida = conocidas.get(cambio.code)
            if conocida is None:
                # Si es nueva, la trae la ingesta nocturna.
                continue

            estaba_activa = _esta_activa(conocida.status_id)
            queda_activa = cambio.status_code in ACTIVE_TENDER_STATUSES

            if queda_activa and not estaba_activa:
                # Reapertura (p. ej. un segundo llamado). Qdrant guarda solo
                # activas, así que no hay punto al que escribirle: hay que
                # reindexarla entera, y eso lo hace `_actualizar` del ingest al
                # ver el cambio de estado. Por eso **no** se toca SQL: si se la
                # marcara activa acá, el ingest la vería "sin cambios" y el punto
                # no volvería nunca.
                a_reencolar.append(cambio.code)
                resultado.reabiertas += 1
                continue

            if queda_activa:
                payloads[conocida.id] = {
                    "status_code": cambio.status_code,
                    "closing_at": to_utc_epoch(cambio.closing_at),
                }
                if _cambio_posterior_a_la_bajada(cambio, conocida):
                    a_reencolar.append(cambio.code)
            else:
                # Borrar un punto que ya no existe no es un error, así que no
                # hace falta saber si estaba indexada.
                a_borrar.append(conocida.id)

            a_sobrescribir.append(cambio)

        # Clave foránea de `tender`: tiene que existir antes del UPDATE.
        for status_id, status_code in sorted(
            {(c.status_id, c.status_code) for c in a_sobrescribir}
        ):
            await self.repo.get_or_create_status(status_id, status_code)

        # Qdrant antes que SQL, igual que en la ingesta: las dos escrituras no
        # comparten transacción. Si SQL falla después, la corrida siguiente ve el
        # mismo cambio en el listado y vuelve a escribir las dos.
        await self.tender_vector_repo.delete_many(a_borrar)
        await self.tender_vector_repo.set_payloads(payloads)
        resultado.sacadas_del_indice = len(a_borrar)

        if a_sobrescribir:
            resultado.actualizadas = await self.repo.overwrite_statuses(a_sobrescribir)
        if a_reencolar:
            resultado.reencoladas = await self.cola.reencolar(a_reencolar)
        return resultado
