"""Aplica a las licitaciones guardadas el estado, el cierre y el llamado del listado.

La ingesta nocturna solo descubre licitaciones nuevas: una ya procesada no se
vuelve a mirar. Sin esto, una desierta o cancelada seguía figurando publicada
hasta su cierre original, y una con el plazo ampliado se cerraba con la fecha
vieja mientras todavía se podía postular.

Se escribe desde el **listado**, sin pedir el detalle: estado y cierre vienen
ahí. Lo que solo trae el detalle (descripción, partidas) no se puede saber desde
el listado; para eso se deja la licitación en la cola y el ingest decide, con
`_actualizar`, si cambió el texto.

Desde el plan 305 cada código listado deja además un **puntero** en la cola
(`tender_metadata`): las publicadas que no tenemos quedan como `nueva`, sin
esperar al listado nocturno, y las pendientes que dejaron de estar activas pasan
a terminal sin gastar intentos.

El llamado vigente y el cierre de cada llamado (plan 233, decisión 3) también
vienen en el listado. Se registran en una escritura aparte que no mueve
`updated_at`: ese campo dispara la regeneración del análisis de Gemini y el
llamado no cambia lo que se pide.
"""

from collections.abc import Callable
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
    Intencion,
    PunteroDeCambio,
    ResultadoSyncEstados,
)
from app.shared.constants import ACTIVE_TENDER_STATUSES, TENDER_STATUS_CODE_BY_ID
from app.shared.datetime_utils import to_utc_epoch, utc_now_naive


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


def _puntero(cambio: CambioDeEstado, intencion: Intencion) -> PunteroDeCambio:
    return PunteroDeCambio(
        code=cambio.code,
        status_code=cambio.status_code,
        changed_at=cambio.changed_at,
        intencion=intencion,
    )


class SyncTenderStatusesUseCase:
    def __init__(
        self,
        repository: ITenderStatusSyncRepository,
        tender_vector_repo: ITenderVectorRepository,
        cola: ITenderIngestionQueue,
        reloj: Callable[[], datetime] = utc_now_naive,
    ) -> None:
        self.repo = repository
        self.tender_vector_repo = tender_vector_repo
        self.cola = cola
        self.reloj = reloj

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
        a_registrar_llamado: list[CambioDeEstado] = []
        a_registrar_ofertas: list[CambioDeEstado] = []
        punteros: list[PunteroDeCambio] = []
        ahora = self.reloj()

        for cambio in cambios:
            conocida = conocidas.get(cambio.code)
            queda_activa = cambio.status_code in ACTIVE_TENDER_STATUSES
            if conocida is None:
                # No la tenemos: solo deja el puntero. Mismo filtro que el
                # listado nocturno, que descarta las de cierre vencido.
                abierta = queda_activa and cambio.closing_at > ahora
                punteros.append(
                    _puntero(cambio, Intencion.NUEVA if abierta else Intencion.INACTIVA)
                )
                continue

            # El llamado se registra en toda conocida, también en una reapertura:
            # no cambia el estado, así que el ingest sigue viendo la diferencia
            # que lo hace reindexar (ver la rama de abajo).
            if cambio.trae_llamado:
                a_registrar_llamado.append(cambio)

            # La cifra, igual: toda conocida que la traiga. El 0 es una cifra.
            if cambio.received_offers_count is not None:
                a_registrar_ofertas.append(cambio)

            estaba_activa = _esta_activa(conocida.status_id)

            if queda_activa and not estaba_activa:
                # Reapertura (p. ej. un segundo llamado). Qdrant guarda solo
                # activas, así que no hay punto al que escribirle: hay que
                # reindexarla entera, y eso lo hace `_actualizar` del ingest al
                # ver el cambio de estado. Por eso **no** se toca SQL: si se la
                # marcara activa acá, el ingest la vería "sin cambios" y el punto
                # no volvería nunca.
                punteros.append(_puntero(cambio, Intencion.REABIERTA))
                resultado.reabiertas += 1
                continue

            if queda_activa:
                payloads[conocida.id] = {
                    "status_code": cambio.status_code,
                    "closing_at": to_utc_epoch(cambio.closing_at),
                }
                punteros.append(_puntero(cambio, Intencion.ACTUALIZAR_SI_CAMBIO))
            else:
                # Borrar un punto que ya no existe no es un error, así que no
                # hace falta saber si estaba indexada.
                a_borrar.append(conocida.id)
                punteros.append(_puntero(cambio, Intencion.INACTIVA))

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
        if a_registrar_llamado:
            # Después del estado, y aparte: no mueve `updated_at`.
            resultado.llamados_actualizados = await self.repo.overwrite_call_info(
                a_registrar_llamado
            )
        if a_registrar_ofertas:
            # También aparte y sin mover `updated_at`.
            resultado.ofertas_revisadas = (
                await self.repo.overwrite_received_offers_count(a_registrar_ofertas)
            )
        # Al final: el puntero de una conocida se compara con lo que el ingest
        # bajó, no con lo que se acaba de escribir arriba.
        if punteros:
            cola = await self.cola.registrar_punteros(punteros)
            resultado.nuevas = cola.nuevas
            resultado.reencoladas = cola.actualizar
            resultado.descartadas = cola.descartadas
        return resultado
