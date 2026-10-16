"""Sincronización de estados de licitaciones ya guardadas, para correr como cron.

Qué resuelve
------------
`sync_diaria.py` solo **descubre** licitaciones nuevas: una ya procesada no se
vuelve a mirar. Sin este cron, una desierta o cancelada seguía figurando
publicada (y generando alertas) hasta su cierre original, y una con el plazo
ampliado se cerraba con la fecha vieja mientras todavía se podía postular.

Qué hace, en orden
------------------
1. **Registra la corrida** en `sync_estados_run`, como incompleta. Si vence el
   tope o el proceso muere, la fila queda y cuenta para la racha.
2. **Lista lo que cambió** en las últimas `--ventana-horas` (listado por
   `ttl_cambio_ms`, sin filtro de estado). Cuesta una petición cada 10
   licitaciones (ver `TAMANO_PAGINA`); no pide el detalle.
3. **Aplica cada página apenas llega** (plan 305), con
   `SyncTenderStatusesUseCase`: borra del índice la que dejó de estar activa,
   actualiza el payload de la que sigue activa y deja en la cola un puntero por
   cada código. Las publicadas que no tenemos quedan como `nueva`; las que
   tenemos y cambiaron después de la última bajada, como `actualizar`. La
   ingesta baja el detalle de las dos. Antes se aplicaba todo al terminar el
   listado, y una corrida que vencía el tope en hora punta lo perdía todo.
4. **Refresca la lista oficial de anexos** de esa misma página (plan 233,
   decisión 1): el listado ya trae `documentos`, así que no cuesta peticiones.
   Aislado: si falla, estados y cierres ya quedaron aplicados.
5. **Marca vencidas.** Después de aplicar, para que un plazo ampliado no se
   cierre con la fecha vieja. Antes lo hacía `sync_diaria`.
6. **Cierra la corrida** con lo listado y las peticiones hechas.

Sobre la ventana
----------------
`ttl_cambio_ms` se cuenta siempre hacia atrás desde ahora: **no admite cursor**.
Por eso la ventana (2 h por defecto) es más ancha que el intervalo del cron
(1 h): una corrida perdida la cubre la siguiente, y reaplicar un cambio es
idempotente.

El volumen manda sobre el tamaño. Medido el 2026-09-29 a mediodía: **1.620
cambios en una hora** (661 publicadas, 535 cerradas, 64 desiertas, 24
canceladas) y 3.090 en dos. Medido el 2026-10-13 en hora punta: ~2.100 cambios
en 2 h, y a 10 por página y ~13,5 s por página son ~210 páginas y unos 47 min,
justo bajo el tope de 50 min de entonces (hoy 55). Con 20 por página la mitad de las páginas daba 504
y la corrida vencía el tope. El techo es 6 h porque la API
corta el listado en 10.000 resultados y a ese ritmo 6 h ya rondan los 9.000.

No escribe en `ingestion_run` ni toca el cursor: `sync_diaria` se niega a correr
si ve una corrida en `running`, y compartir la tabla la bloquearía cada vez que
coincidan. Los dos crons pueden correr a la vez: este escribe punteros en la
cola y la ingesta los consume.

Uso
---
    python -m scripts.sync_estados                              # local
    python -m scripts.sync_estados --confirmar-produccion       # el cron

Códigos de salida
-----------------
Railway manda un correo de "crashed" por cada salida distinta de 0, así que el
1 se reserva para lo que pide que alguien mire:

- **0**: el listado vino completo, o vino incompleto y es pasajero. En hora
  punta la API responde 504 casi cada hora (medido el 2026-10-05: once corridas
  seguidas entre 10:00 y 18:00), y la ventana de 2 h hace que la corrida
  siguiente vuelva a pedir lo que faltó. Lo avisa en el log con la cuenta.
- **1**: se juntaron `--incompletas-toleradas` incompletas seguidas (horas sin
  mirar), se tocó el techo de `--limite` (la configuración se queda corta y
  esperar no lo arregla) o venció el tope de tiempo. Las páginas que llegaron
  quedan aplicadas igual.
- **2**: se negó a correr contra una base no local o la ventana es inválida.

La racha de incompletas se cuenta en la tabla `sync_estados_run`. Un fallo al
refrescar la lista de anexos no cambia el código: queda en el log y la corrida
siguiente lo reintenta.
"""

import argparse
import asyncio
import sys
import time
from collections.abc import Awaitable, Callable, Coroutine
from datetime import timedelta
from typing import Any
from uuid import UUID

from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.use_cases.sync_tender_statuses import SyncTenderStatusesUseCase
from app.application.use_cases.tender_attachments.sync_official_attachments import (
    listas_desde_cambios,
)
from app.config import settings
from app.domain.models.cambio_estado import CambioDeEstado, ResultadoSyncEstados
from app.infrastructure.repositories.qdrant_tender_repository import (
    QdrantTenderRepository,
)
from app.infrastructure.repositories.sync_estados_run_repository import (
    SyncEstadosRunRepository,
)
from app.infrastructure.repositories.tender_repository import TenderRepository
from app.infrastructure.services.tenders.tender_ingestion_service import (
    ListadoCambios,
    TenderIngestionService,
)
from scripts.ingesta_compartida import (
    aplicar_documentos_oficiales,
    construir_servicio,
    imprimir_resumen,
    marcar_vencidas,
    preparar_destino,
)
from scripts.sync_diaria import verificar_destino

# Los valores por defecto de ventana, tope de ítems, tope de tiempo e
# incompletas toleradas vienen de `SYNC_ESTADOS_VENTANA_HORAS`,
# `SYNC_ESTADOS_LIMITE`, `SYNC_ESTADOS_TIMEOUT_MINUTOS` y
# `SYNC_ESTADOS_INCOMPLETAS_TOLERADAS` (ver `app/config.py`): 2 h, 9.000 (bajo
# los 10.000 en que corta la API), 55 min (el tope tiene que quedar bajo el intervalo
# de 1 h; vencerlo cuenta como incompleta) y 3.
MAX_VENTANA_HORAS = 6.0


def validar_ventana(horas: float) -> str | None:
    """El motivo para rechazar la ventana, o `None` si sirve."""
    if horas <= 0:
        return "La ventana tiene que ser mayor que cero."
    if horas > MAX_VENTANA_HORAS:
        return (
            f"La ventana no puede pasar de {MAX_VENTANA_HORAS:g} h: la API corta "
            "el listado en 10.000 resultados, y en hora punta hay ~1.600 cambios "
            "por hora. El resto se perdería en silencio."
        )
    return None


def codigo_por_racha(seguidas: int | None, *, toleradas: int) -> int:
    """El código de salida de una corrida incompleta según la racha.

    `seguidas` incluye a esta corrida. `None` es que no hay historial (la fila
    no se pudo cerrar), y entonces se avisa con 1.
    """
    if seguidas is None or seguidas >= toleradas:
        return 1
    return 0


async def con_tope(
    corutina: Coroutine[Any, Any, int],
    segundos: float,
    codigo_al_vencer: Callable[[], int] | None = None,
) -> int:
    """Corre con un tope de tiempo y decide el código de salida al vencer.

    Railway no termina una corrida colgada y omite las siguientes: sin tope, un
    cron que espera una respuesta que no llega deja de correr para siempre.

    Vencer el tope es una corrida incompleta más (plan 305): las páginas que
    llegaron ya se aplicaron y la ventana de la siguiente cubre el resto.
    `codigo_al_vencer()` devuelve 0 mientras la racha de incompletas esté
    dentro de lo tolerado. Sin él, sale con 1.
    """
    try:
        return await asyncio.wait_for(corutina, timeout=segundos)
    except TimeoutError:
        codigo = codigo_al_vencer() if codigo_al_vencer is not None else 1
        nivel = "AVISO" if codigo == 0 else "ERROR"
        print(
            f"\n{nivel}: la corrida superó el tope de {segundos / 60:.0f} min y se "
            "canceló. Las páginas que alcanzaron a llegar ya se aplicaron y la "
            "corrida quedó registrada como incompleta; la siguiente vuelve a "
            "listar la ventana."
        )
        return codigo


AlRecibir = Callable[[list[CambioDeEstado]], Awaitable[None]]


async def sincronizar_estados(
    args: argparse.Namespace,
    *,
    listar: Callable[[timedelta, int, AlRecibir], Awaitable[ListadoCambios]],
    aplicar: Callable[[list[CambioDeEstado]], Awaitable[ResultadoSyncEstados]],
    marcar_vencidas: Callable[[], Awaitable[int]],
    preparar_destino: Callable[[], Awaitable[None]] | None = None,
    aplicar_anexos: Callable[[list[CambioDeEstado]], Awaitable[int]] | None = None,
    abrir_corrida: Callable[[], Awaitable[UUID]] | None = None,
    cerrar_corrida: Callable[[UUID, bool, int, int | None], Awaitable[int]]
    | None = None,
    peticiones: Callable[[], int] | None = None,
    metricas: Callable[[], dict[str, Any]] | None = None,
    al_vencer: Callable[[int | None], None] | None = None,
) -> int:
    """Orquesta la corrida y devuelve el código de salida.

    `metricas()` devuelve el resumen de peticiones del cliente, que va en la
    línea `RESUMEN` del log junto con lo que hizo la corrida.

    Recibe sus colaboradores en vez de construirlos, igual que `sync_diaria`:
    el orden de las etapas y el código de salida se prueban sin Postgres ni
    Qdrant.

    `listar` entrega cada página a `al_recibir` antes de pedir la siguiente, y
    cada página se aplica ahí mismo (plan 305): si la corrida se corta después,
    lo aplicado queda.

    `abrir_corrida` registra la corrida al empezar y `cerrar_corrida(id,
    completo, listadas, peticiones)` la cierra y devuelve cuántas incompletas van
    seguidas contándola. Si vence el tope, se cierra como incompleta con lo que
    alcanzó a listar, y `al_vencer` recibe cuántas incompletas van seguidas
    (`None` sin historial) para que `con_tope` decida el código de salida. Sin
    ellos no hay historial y cualquier incompleta sale con 1.
    """
    inicio = time.perf_counter()
    if preparar_destino is not None:
        await preparar_destino()

    corrida = await abrir_corrida() if abrir_corrida is not None else None
    resultado = ResultadoSyncEstados()
    aplicadas = 0
    anexos = {"refrescadas": 0, "fallo": None}

    async def al_recibir(cambios: list[CambioDeEstado]) -> None:
        nonlocal aplicadas
        if not cambios:
            return
        resultado.sumar(await aplicar(cambios))
        aplicadas += len(cambios)
        # Aislado: estados y cierres de la página ya están aplicados. Un fallo
        # acá no puede deshacerlos ni cortar el listado.
        if aplicar_anexos is not None:
            try:
                anexos["refrescadas"] += await aplicar_anexos(cambios)
            except Exception as error:
                anexos["fallo"] = error

    async def cerrar(completo: bool, listadas: int) -> int:
        if corrida is None or cerrar_corrida is None:
            return 0
        return await cerrar_corrida(
            corrida, completo, listadas, peticiones() if peticiones else None
        )

    def resumir(**extra: Any) -> None:
        imprimir_resumen(
            "sync_estados",
            {
                "ventana_h": args.ventana_horas,
                "aplicadas": aplicadas,
                "conocidas": resultado.conocidas,
                "actualizadas": resultado.actualizadas,
                "sacadas_del_indice": resultado.sacadas_del_indice,
                "reabiertas": resultado.reabiertas,
                "reencoladas": resultado.reencoladas,
                "nuevas": resultado.nuevas,
                "descartadas": resultado.descartadas,
                "duracion_min": round((time.perf_counter() - inicio) / 60, 1),
                "api": metricas() if metricas else None,
                **extra,
            },
        )

    try:
        listado = await listar(
            timedelta(hours=args.ventana_horas), args.limite, al_recibir
        )
    except asyncio.CancelledError:
        # Venció el tope: la fila queda cerrada como incompleta y cuenta para la
        # racha, en vez de desaparecer como antes.
        seguidas = await cerrar(False, aplicadas)
        if al_vencer is not None:
            historial = corrida is not None and cerrar_corrida is not None
            al_vencer(seguidas if historial else None)
        resumir(cancelada=True, completo=False)
        raise

    print(
        f"{listado.listadas} cambios listados ({listado.ilegibles} ilegibles) en "
        f"las últimas {args.ventana_horas:g} h."
    )
    print(
        f"{resultado.conocidas} conocidas: {resultado.actualizadas} actualizadas, "
        f"{resultado.llamados_actualizados} con llamado actualizado, "
        f"{resultado.sacadas_del_indice} sacadas del índice, "
        f"{resultado.reabiertas} reabiertas, {resultado.reencoladas} reencoladas. "
        f"En la cola: {resultado.nuevas} nuevas, {resultado.descartadas} "
        "descartadas."
    )

    vencidas = None
    if not args.sin_marcar:
        vencidas = await marcar_vencidas()
        print(f"Vencidas marcadas como cerradas: {vencidas}")

    if aplicar_anexos is not None:
        if anexos["fallo"] is None:
            print(f"Listas de anexos refrescadas: {anexos['refrescadas']}")
        else:
            error = anexos["fallo"]
            print(
                "\nAVISO: no se pudo refrescar la lista de anexos "
                f"({type(error).__name__}: {error}).\n"
                "Estados y cierres ya quedaron aplicados; la corrida siguiente lo\n"
                "reintenta."
            )

    techo = listado.listadas >= args.limite
    seguidas = await cerrar(listado.completo, listado.listadas)
    historial = corrida is not None and cerrar_corrida is not None
    if techo:
        print(
            f"\nAVISO: se listaron {listado.listadas}, que es el techo de la corrida.\n"
            "Quedaron cambios sin mirar. Achica --ventana-horas o sube --limite\n"
            "(sin pasar de 10.000, donde corta la API)."
        )
        codigo = 1
    elif listado.completo:
        codigo = 0
    elif historial and seguidas < args.incompletas_toleradas:
        print(
            "\nAVISO: el listado quedó incompleto (la API cortó la paginación o se\n"
            "agotó la cuota). Lo que llegó se aplicó; la corrida siguiente vuelve\n"
            f"a pedir la ventana. Incompletas seguidas: {seguidas} de "
            f"{args.incompletas_toleradas}\n"
            "toleradas antes de salir con error."
        )
        codigo = 0
    else:
        print(
            f"\nERROR: el listado quedó incompleto ({seguidas or 1} corridas seguidas).\n"
            "La API de Mercado Público lleva horas fallando o la cuota se agotó:\n"
            "hay cambios de estado sin mirar. Lo que llegó se aplicó."
        )
        codigo = 1

    print(f"\nCorrida en {(time.perf_counter() - inicio) / 60:.1f} min.")
    resumir(
        cancelada=False,
        completo=listado.completo,
        listadas=listado.listadas,
        ilegibles=listado.ilegibles,
        vencidas=vencidas,
        incompletas_seguidas=seguidas,
        anexos_fallaron=anexos["fallo"] is not None,
        codigo=codigo,
    )
    return codigo


async def _aplicar(
    engine: AsyncEngine,
    qdrant: AsyncQdrantClient,
    servicio: TenderIngestionService,
    cambios: list[CambioDeEstado],
) -> ResultadoSyncEstados:
    async with AsyncSession(engine) as session:
        caso = SyncTenderStatusesUseCase(
            repository=TenderRepository(session),
            tender_vector_repo=QdrantTenderRepository(
                client=qdrant, vector_size=settings.embedding_vector_size
            ),
            cola=servicio,
        )
        return await caso.execute(cambios)


async def _abrir(engine: AsyncEngine) -> UUID:
    async with AsyncSession(engine) as session:
        return await SyncEstadosRunRepository(session).abrir()


async def _cerrar(
    engine: AsyncEngine,
    corrida: UUID,
    completo: bool,
    listadas: int,
    peticiones: int | None,
) -> int:
    async with AsyncSession(engine) as session:
        return await SyncEstadosRunRepository(session).cerrar(
            corrida, completo=completo, listadas=listadas, peticiones=peticiones
        )


async def _correr(
    args: argparse.Namespace, al_vencer: Callable[[int | None], None]
) -> int:
    """Arma las piezas reales y cierra lo que abrió.

    Railway omite la ejecución siguiente de un cron si la anterior sigue viva:
    dejar el engine o el cliente de Qdrant abiertos es un cron que deja de correr.
    """
    servicio, engine, qdrant = construir_servicio(con_embeddings=False)
    try:
        return await sincronizar_estados(
            args,
            listar=servicio.listar_cambios,
            aplicar=lambda cambios: _aplicar(engine, qdrant, servicio, cambios),
            marcar_vencidas=lambda: marcar_vencidas(engine, qdrant),
            preparar_destino=lambda: preparar_destino(engine, qdrant),
            aplicar_anexos=lambda cambios: aplicar_documentos_oficiales(
                engine, listas_desde_cambios(cambios)
            ),
            abrir_corrida=lambda: _abrir(engine),
            cerrar_corrida=lambda corrida, completo, listadas, peticiones: _cerrar(
                engine, corrida, completo, listadas, peticiones
            ),
            peticiones=lambda: servicio.client.peticiones,
            metricas=servicio.client.resumen,
            al_vencer=al_vencer,
        )
    finally:
        await engine.dispose()
        await qdrant.close()


def construir_parser() -> argparse.ArgumentParser:
    """Los defaults salen de la configuración, así se ajustan por entorno."""
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    p.add_argument(
        "--ventana-horas",
        type=float,
        default=settings.sync_estados_ventana_horas,
        help=(
            "cuántas horas hacia atrás mirar (SYNC_ESTADOS_VENTANA_HORAS, "
            f"{settings.sync_estados_ventana_horas:g}; máx. {MAX_VENTANA_HORAS:g})"
        ),
    )
    p.add_argument(
        "--limite",
        type=int,
        default=settings.sync_estados_limite,
        help=(
            "tope de ítems del listado (SYNC_ESTADOS_LIMITE, "
            f"{settings.sync_estados_limite})"
        ),
    )
    p.add_argument(
        "--sin-marcar",
        action="store_true",
        help="omitir el barrido de vencidas",
    )
    p.add_argument(
        "--confirmar-produccion",
        action="store_true",
        help="requerido si la base no es local",
    )
    p.add_argument(
        "--timeout-minutos",
        type=float,
        default=settings.sync_estados_timeout_minutos,
        help=(
            "tope de la corrida (SYNC_ESTADOS_TIMEOUT_MINUTOS, "
            f"{settings.sync_estados_timeout_minutos:g})"
        ),
    )
    p.add_argument(
        "--incompletas-toleradas",
        type=int,
        default=settings.sync_estados_incompletas_toleradas,
        help=(
            "corridas incompletas seguidas que salen con 0 antes de dar error "
            "(SYNC_ESTADOS_INCOMPLETAS_TOLERADAS, "
            f"{settings.sync_estados_incompletas_toleradas})"
        ),
    )
    return p


def main() -> None:
    args = construir_parser().parse_args()

    print(f"Base de datos : {settings.database_url.split('@')[-1]}\n")

    mensaje = validar_ventana(args.ventana_horas) or verificar_destino(
        settings.database_url, confirmar_produccion=args.confirmar_produccion
    )
    if mensaje:
        print(mensaje, file=sys.stderr)
        sys.exit(2)

    # La racha la conoce `sincronizar_estados` al cerrar la fila cancelada; el
    # código de salida lo decide `con_tope`, que es quien atrapa el tope.
    racha: list[int | None] = [None]

    def anotar(seguidas: int | None) -> None:
        racha[0] = seguidas

    sys.exit(
        asyncio.run(
            con_tope(
                _correr(args, anotar),
                segundos=args.timeout_minutos * 60,
                codigo_al_vencer=lambda: codigo_por_racha(
                    racha[0], toleradas=args.incompletas_toleradas
                ),
            )
        )
    )


if __name__ == "__main__":
    main()
