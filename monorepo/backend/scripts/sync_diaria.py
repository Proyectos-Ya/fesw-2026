"""Sincronización diaria de licitaciones, para correr como cron aislado.

Qué resuelve
------------
La ingesta vivía dentro del proceso de la API (`TenderScheduler`, en el
`lifespan`): obligaba a un solo worker, metía horas diarias de CPU y red en el
proceso que atiende a los usuarios y sondeaba la base cada 2 segundos. Se sacó
de ahí; este script, corriendo como cron de Railway, es el único camino.

Y, sobre todo, **usa el cursor** (`ingestion_run`): cada corrida pide desde donde
terminó la última buena, en vez de "las últimas 24 h contadas desde ahora". Con
un cron eso importa, porque una ejecución que no corre deja un hueco que nadie
vuelve a mirar.

Dos modos (plan 305)
--------------------
El cron corre cada 2 h (`0 */2 * * *`). Con `--modo auto`, la corrida de las
06:00 UTC (03:00 en Chile) es la **nocturna** y el resto son **frecuentes**.

Desde el plan 305, el cron de estados lista los cambios cada hora y deja en la
cola qué hay que bajar (`nueva` o `actualizar`). Esta ingesta baja los detalles.

**Frecuente** (tope de 100 min, sale con 0 al vencer):

1. Si hay otra corrida viva (la nocturna puede seguir vaciando la cola), sale
   con 0 sin hacer nada.
2. Vacía la cola con lo que nunca falló, las `nueva` primero, con 2 intentos
   HTTP por detalle. Una que falla queda para la noche.

**Nocturna** (tope de 6 h):

1. Cierra las corridas colgadas y se niega si hay otra en curso.
2. **Red de seguridad.** Lista lo publicado en la ventana del cursor, en tramos
   de 6 h. Cada tramo listado entero cierra su fila (`kind='tramo'`) en `ok` y
   mueve el cursor: si la corrida se corta después, lo listado no se vuelve a
   pedir. Al primer tramo incompleto se detiene. Cada tramo refresca también la
   lista oficial de anexos, aislado: si falla, el cursor ya avanzó.
3. **Vacía la cola** con 3 intentos HTTP por detalle.
4. **Reintentos.** Una pasada, con 1 intento, sobre lo que falló antes de esta
   corrida. Al quinto reintento nocturno sin éxito, la fila pasa a terminal.

La corrida entera tiene su propia fila (`kind='nocturna'`), que queda en
`running` mientras se vacía la cola: así una frecuente que arranque en el medio
no se cruza con esta. Esa fila no mueve el cursor.

(Ya no marca vencidas: lo hace `sync_estados.py`, **después** de corregir los
cierres con el listado de cambios.)

Sobre `--limite`, que es la trampa de este script
-------------------------------------------------
Medido el 2026-09-10: en un día hábil cambian ~5.600 licitaciones publicadas.
`MERCADOPUBLICO_FETCHING_LIMIT` vale **2.000** por defecto, así que con ese valor
el listado se corta, la corrida queda `partial`, el cursor no avanza y la
sincronización **no progresa nunca**. Es un fallo silencioso salvo por el aviso
que este script imprime. En producción hay que subir esa variable por encima del
volumen real, con margen.

Uso
---
    python -m scripts.sync_diaria --modo frecuente              # prueba local
    python -m scripts.sync_diaria --modo nocturna --limite 100  # prueba local
    python -m scripts.sync_diaria --confirmar-produccion        # lo que ejecuta el cron

Tres protecciones para correr sin supervisión:

- **Se niega contra una base que no sea local** salvo `--confirmar-produccion`.
  Una prueba local con un `.env` que quedó apuntando a producción escribía ahí sin
  avisar; el servicio de Railway lleva el flag en su `startCommand`.
- **Timeout duro** (`--timeout-minutos`: 360 la nocturna, 100 la frecuente).
  Railway no termina una corrida colgada y **omite todas las siguientes**, así
  que un cron que se queda esperando deja de correr para siempre. Al vencer, la
  corrida cierra su fila como `failed`; los tramos ya listados movieron el
  cursor.

- **Una sola corrida a la vez.** Las `running` más viejas que el tope de la
  nocturna se cierran como `failed` (su proceso murió); si queda una más nueva,
  la nocturna se niega con 1 y la frecuente sale con 0. `--forzar` las cierra
  todas, para cuando se quitó un deploy a mano.
- **Presupuesto** (`--max-peticiones`). La corrida se detiene al llegar a ese
  número de peticiones a Mercado Público, y cada corrida guarda las que hizo en
  `ingestion_run.requests`.

Códigos de salida: 0 si la ventana se listó entera, aunque queden licitaciones en
la cola por errores de red (las retoma la corrida siguiente); 1 si un tramo quedó
a medias, se agotó la cuota, venció el tope de la nocturna o había otra nocturna
en curso; 2 si se negó a correr contra una base no local. En un cron de Railway
ese código es la única señal visible de que algo salió mal.
"""

import argparse
import asyncio
import sys
import time
from collections.abc import Awaitable, Callable, Coroutine
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from app.application.services.tender_ingestion_service import (
    ITenderIngestionService,
    ModoCola,
)
from app.config import settings
from app.domain.models.tender_ingestion_dto import DocumentoOficialDTO
from app.shared.constants import TENDER_STATUSES
from app.shared.datetime_utils import utc_now_naive
from scripts.ingesta_compartida import (
    EmbeddingsContados,
    ResultadoRondas,
    aplicar_documentos_oficiales,
    construir_servicio,
    contar_pendientes,
    es_local,
    preparar_destino,
    vaciar_cola,
)

# Medido en local (2026-09-15): el detalle tarda 1,7-17 s por llamada y listar
# ~12 s por página de 20, así que un día hábil (~4.500) proyecta ~45 min listando
# y ~2,5 h de detalle con concurrencia 10: unas 3-3,5 h. Seis horas dejan margen
# para una API lenta y siguen lejos de pisar la corrida del día siguiente.
DEFAULT_TIMEOUT_MINUTOS = 360


def verificar_destino(database_url: str, *, confirmar_produccion: bool) -> str | None:
    """El motivo para negarse a correr, o `None` si se puede.

    Mismo criterio que `bootstrap_corpus.py`: lo que escribe en una base
    compartida tiene que pedirse explícitamente, no pasar por olvidar una
    variable de entorno.
    """
    if confirmar_produccion or es_local(database_url):
        return None
    host = urlsplit(database_url).hostname or "desconocido"
    return (
        f"La base ({host}) no es local y falta --confirmar-produccion.\n"
        "Correr la sincronización contra una base compartida es deliberado: si\n"
        "esto era una prueba local, revisa DATABASE_URL en tu .env."
    )


# Tope de la corrida frecuente: queda bajo el intervalo de 2 h del cron, para que
# la siguiente no se encuentre con esta todavía viva.
TIMEOUT_FRECUENTE_MINUTOS = 100

# Tramos de la red de seguridad nocturna. Cada tramo listado entero mueve el
# cursor, así que una corrida que se corta pierde a lo más un tramo. Seis horas
# de un día hábil son ~1.400 publicaciones, ~70 páginas: lejos del techo.
TRAMO_HORAS = 6.0

# La corrida de las 06:00 UTC (03:00 en Chile) es la nocturna: lista, vacía la
# cola y reintenta. El resto, cada 2 h, solo vacía la cola.
HORA_NOCTURNA_UTC = 6

# Intentos HTTP por detalle según la pasada. Cada intento contra un 504 gasta
# cuota: de día se insiste poco, de noche un poco más, y la pasada de reintentos
# es un solo intento por noche.
INTENTOS_FRECUENTE = 2
INTENTOS_NOCTURNA = 3
INTENTOS_REINTENTOS = 1

# La nocturna poda la cola una vez por semana (domingo, con poco movimiento).
DIA_RETENCION = 6


async def con_timeout(
    corutina: Coroutine[Any, Any, int],
    segundos: float,
    *,
    codigo_al_vencer: int = 1,
) -> int:
    """Corre la sincronización con un tope de tiempo.

    `asyncio.wait_for` cancela la corrida, que alcanza a cerrar su fila de
    `ingestion_run` como `failed`, y el `finally` de `_correr` cierra el engine y
    el cliente de Qdrant: el proceso termina de verdad, que es lo que Railway
    necesita para lanzar la ejecución siguiente.

    La corrida frecuente vence con 0: lo que no alcanzó queda en la cola para la
    siguiente, y Railway mandaría un correo de "crashed" cada 2 h.
    """
    try:
        return await asyncio.wait_for(corutina, timeout=segundos)
    except TimeoutError:
        print(
            f"\nAVISO: la corrida superó el tope de {segundos / 60:.0f} min y se "
            "canceló. Los tramos ya listados movieron el cursor; lo que quedó en "
            "la cola lo retoma la corrida siguiente."
        )
        return codigo_al_vencer


def elegir_modo(ahora: datetime, *, hora_nocturna: int = HORA_NOCTURNA_UTC) -> str:
    """`nocturna` en la corrida de la hora nocturna (UTC), `frecuente` en el resto."""
    return "nocturna" if ahora.hour == hora_nocturna else "frecuente"


def partir_en_tramos(
    desde: datetime, hasta: datetime, tramo: timedelta
) -> list[tuple[datetime, datetime]]:
    """La ventana en tramos contiguos de `tramo`, el último más corto si sobra."""
    tramos = []
    inicio = desde
    while inicio < hasta:
        fin = min(inicio + tramo, hasta)
        tramos.append((inicio, fin))
        inicio = fin
    return tramos


async def _preparar_y_reservar(
    args: argparse.Namespace,
    servicio: ITenderIngestionService,
    preparar_destino: Callable[[], Awaitable[None]] | None,
) -> bool:
    """Cierra las corridas colgadas y dice si hay otra viva.

    El corte de colgadas es el tope de la **nocturna** en los dos modos: una
    frecuente que lo calculara con su propio tope cerraría como colgada una
    nocturna que todavía está vaciando la cola. `--forzar` cierra todas, para
    cuando se sabe que no hay otra viva.
    """
    if preparar_destino is not None:
        await preparar_destino()
    forzar = getattr(args, "forzar", False)
    corte = (
        utc_now_naive()
        if forzar
        else utc_now_naive() - timedelta(minutes=DEFAULT_TIMEOUT_MINUTOS)
    )
    if cerradas := await servicio.cerrar_corridas_colgadas(corte):
        print(f"--- Corridas colgadas cerradas como 'failed': {cerradas} ---")
    return await servicio.hay_corrida_en_curso()


def _avisos_del_vaciado(resultado: ResultadoRondas) -> None:
    print(
        f"{resultado.procesadas} procesadas en {resultado.rondas} rondas, "
        f"{resultado.pendientes} pendientes."
    )
    if resultado.cuota_agotada:
        print(
            "\nAVISO: se agotó la cuota del ticket. Lo encolado no se pierde:\n"
            "la corrida siguiente lo retoma desde la cola."
        )
    elif resultado.api_caida:
        print(
            "\nAVISO: la API devolvió errores seguidos y se cortó el vaciado sin\n"
            "cobrar intentos a lo que faltaba. Lo retoma la corrida siguiente."
        )
    elif resultado.sin_avance:
        print(
            "\nAVISO: varias rondas seguidas sin avanzar. Hay licitaciones que\n"
            "fallan de forma reproducible; revisa `tender_metadata.last_error`."
        )


async def sincronizar(
    args: argparse.Namespace,
    servicio: ITenderIngestionService,
    *,
    contar: Callable[..., Awaitable[int]],
    preparar_destino: Callable[[], Awaitable[None]] | None = None,
    aplicar_anexos: Callable[[dict[str, list[DocumentoOficialDTO]]], Awaitable[int]]
    | None = None,
    fijar_intentos: Callable[[int], None] | None = None,
    peticiones: Callable[[], int] | None = None,
    purgar: Callable[[], Awaitable[int]] | None = None,
    embeddings: Callable[[], int] | None = None,
) -> int:
    """La corrida nocturna: lista por tramos, vacía la cola y reintenta.

    `purgar`, si viene, poda la cola al final: `_correr` lo pasa una vez por
    semana.

    Recibe sus colaboradores en vez de construirlos: lo que decide si un tramo
    es `ok` o `partial` —y con eso, si el cursor avanza— es lógica que conviene
    poder probar sin levantar Postgres ni Qdrant.

    `contar(modo, antes_de)` cuenta la parte de la cola que toma cada pasada.
    """
    inicio = time.perf_counter()
    if await _preparar_y_reservar(args, servicio, preparar_destino):
        print(
            "\nERROR: hay otra corrida en 'running' que empezó hace menos de "
            f"{DEFAULT_TIMEOUT_MINUTOS} min.\nSi de verdad no está corriendo (por "
            "ejemplo, se quitó el deploy a mano),\nvuelve a lanzar con --forzar."
        )
        return 1

    if getattr(args, "sin_marcar", False):
        # Se acepta sin efecto por un despliegue: un `startCommand` configurado
        # en el panel de Railway puede llevarla, y argparse fallaría sin ella.
        print(
            "--- --sin-marcar ya no tiene efecto: vencidas las marca sync_estados ---"
        )

    desde, hasta = await servicio.ventana_a_sincronizar()
    print(f"--- Ventana: {desde.isoformat()} → {hasta.isoformat()} ---")

    # La fila de la corrida entera: queda en `running` mientras se vacía la cola,
    # y así una frecuente que arranque en el medio no se cruza con esta. No mueve
    # el cursor: eso lo hacen las filas de los tramos.
    run_id = await servicio.registrar_inicio(desde, hasta, kind="nocturna")
    corrida_inicio = utc_now_naive()
    limite = args.limite or settings.mercadopublico_fetching_limit
    tramo = timedelta(hours=getattr(args, "tramo_horas", TRAMO_HORAS))

    try:
        listadas = 0
        nuevas = 0
        todo_ok = True
        anexos_fallaron = False
        for t_desde, t_hasta in partir_en_tramos(desde, hasta, tramo):
            tramo_id = await servicio.registrar_inicio(t_desde, t_hasta, kind="tramo")
            # `por_publicacion=True` y no la ventana de cambios: descubrir
            # licitaciones preguntando "qué se publicó en este rango" es correcto
            # por construcción. Es la red de seguridad de lo que el cron de
            # estados no alcanzó a ver.
            listado = await servicio.fetch_tenders_metadata(
                desde=t_desde,
                hasta=t_hasta,
                por_publicacion=True,
                estado=args.estado or None,
                limite=limite,
            )
            listadas += listado.listadas
            nuevas += listado.nuevas
            estado_tramo = "ok" if listado.completo else "partial"
            await servicio.registrar_fin(
                tramo_id, status=estado_tramo, listed=listado.listadas
            )
            print(
                f"Tramo {t_desde.isoformat()} → {t_hasta.isoformat()}: "
                f"{listado.listadas} listadas, {listado.nuevas} nuevas "
                f"('{estado_tramo}')."
            )

            # Después de cerrar el tramo y aislado: un fallo acá no puede
            # deshacer ni retrasar el cursor, solo cambia el código de salida.
            if aplicar_anexos is not None and listado.documentos:
                try:
                    refrescadas = await aplicar_anexos(listado.documentos)
                    print(f"Listas de anexos refrescadas: {refrescadas}")
                except Exception as error:
                    anexos_fallaron = True
                    print(
                        "\nAVISO: no se pudo refrescar la lista de anexos "
                        f"({type(error).__name__}: {error}).\n"
                        "El tramo y el cursor ya quedaron registrados; la lista se\n"
                        "actualiza igual en la próxima pasada de sync_estados."
                    )

            if not listado.completo:
                todo_ok = False
                if listado.listadas >= limite:
                    print(
                        f"\nAVISO: el tramo tocó el techo de {limite} y el cursor NO "
                        "avanza\nmás allá de él hasta que se suba "
                        "MERCADOPUBLICO_FETCHING_LIMIT\no se acorte --tramo-horas."
                    )
                else:
                    print(
                        "\nAVISO: el tramo quedó incompleto (la API cortó la\n"
                        "paginación). El cursor queda en el último tramo completo\n"
                        "y la corrida siguiente sigue desde ahí."
                    )
                break

        print(f"{listadas} licitaciones listadas, {nuevas} nuevas encoladas.")

        if fijar_intentos is not None:
            fijar_intentos(INTENTOS_NOCTURNA)
        resultado = await vaciar_cola(
            servicio,
            lambda: contar(ModoCola.NUEVAS, None),
            modo=ModoCola.NUEVAS,
        )
        _avisos_del_vaciado(resultado)

        # Reintentos: lo que falló antes de esta corrida, un intento por noche.
        if not resultado.cuota_agotada:
            if fijar_intentos is not None:
                fijar_intentos(INTENTOS_REINTENTOS)
            reintentos = await vaciar_cola(
                servicio,
                lambda: contar(ModoCola.REINTENTOS, corrida_inicio),
                modo=ModoCola.REINTENTOS,
                antes_de=corrida_inicio,
                verboso=False,
            )
            print(
                f"Reintentos nocturnos: {reintentos.procesadas} entraron, "
                f"{reintentos.pendientes} siguen pendientes."
            )
            resultado.procesadas += reintentos.procesadas
            resultado.cuota_agotada = reintentos.cuota_agotada

        estado = "ok" if todo_ok else "partial"
        await servicio.registrar_fin(
            run_id,
            status=estado,
            listed=listadas,
            processed=resultado.procesadas,
            failed=resultado.pendientes,
            requests=peticiones() if peticiones else None,
            embedding_calls=embeddings() if embeddings else None,
        )
    except asyncio.CancelledError:
        await servicio.registrar_fin(
            run_id,
            status="failed",
            requests=peticiones() if peticiones else None,
            embedding_calls=embeddings() if embeddings else None,
        )
        raise

    # Al final y aislado: la corrida ya quedó registrada. Un fallo acá no cambia
    # el código de salida; la poda de la semana siguiente lo cubre.
    if purgar is not None:
        try:
            print(f"Retención de la cola: {await purgar()} filas viejas borradas.")
        except Exception as error:
            print(
                f"\nAVISO: no se pudo podar la cola ({type(error).__name__}: {error})."
            )

    print(f"\nCorrida '{estado}' en {(time.perf_counter() - inicio) / 60:.1f} min.")
    # Pendientes por errores de red no cuentan como fallo: la cola las retoma. La
    # cuota agotada sí, aunque el cursor avance, porque si se repite el ticket no
    # alcanza para el volumen diario y alguien tiene que enterarse.
    ok = estado == "ok" and not resultado.cuota_agotada and not anexos_fallaron
    return 0 if ok else 1


async def vaciar_frecuente(
    args: argparse.Namespace,
    servicio: ITenderIngestionService,
    *,
    contar: Callable[..., Awaitable[int]],
    preparar_destino: Callable[[], Awaitable[None]] | None = None,
    fijar_intentos: Callable[[int], None] | None = None,
    peticiones: Callable[[], int] | None = None,
    embeddings: Callable[[], int] | None = None,
) -> int:
    """La corrida frecuente (cada 2 h): baja el detalle de lo que dejó el cron de
    estados en la cola, sin listar ni tocar el cursor.

    Si la nocturna sigue viva, sale con 0 sin hacer nada: es esperable que la
    nocturna siga vaciando la cola un par de horas, y un 1 mandaría un correo.
    """
    inicio = time.perf_counter()
    if await _preparar_y_reservar(args, servicio, preparar_destino):
        print("Hay otra corrida en curso: esta no hace nada.")
        return 0

    ahora = utc_now_naive()
    run_id = await servicio.registrar_inicio(ahora, ahora, kind="frecuente")
    try:
        if fijar_intentos is not None:
            fijar_intentos(INTENTOS_FRECUENTE)
        resultado = await vaciar_cola(
            servicio,
            lambda: contar(ModoCola.NUEVAS, None),
            modo=ModoCola.NUEVAS,
        )
        _avisos_del_vaciado(resultado)
        # `vaciada` y no `ok`: la versión anterior de este script lee el cursor
        # de cualquier corrida `ok` sin mirar el tipo, y la ventana de esta fila
        # es "ahora". Con `ok`, volver a esa versión saltaría el cursor.
        await servicio.registrar_fin(
            run_id,
            status="vaciada",
            processed=resultado.procesadas,
            failed=resultado.pendientes,
            requests=peticiones() if peticiones else None,
            embedding_calls=embeddings() if embeddings else None,
        )
    except asyncio.CancelledError:
        await servicio.registrar_fin(
            run_id,
            status="failed",
            requests=peticiones() if peticiones else None,
            embedding_calls=embeddings() if embeddings else None,
        )
        raise

    print(f"\nCorrida frecuente en {(time.perf_counter() - inicio) / 60:.1f} min.")
    return 1 if resultado.cuota_agotada else 0


async def _correr(args: argparse.Namespace, modo: str) -> int:
    """Arma las piezas reales y garantiza que el proceso cierre lo que abrió.

    Railway omite la ejecución siguiente de un cron si la anterior sigue viva, así
    que dejar el engine o el cliente de Qdrant abiertos no es un descuido estético:
    es una sincronización que deja de correr.
    """
    servicio, engine, qdrant = construir_servicio()
    cliente = servicio.client
    cliente.max_peticiones = args.max_peticiones

    def fijar_intentos(intentos: int) -> None:
        cliente.intentos_detalle = intentos

    def embeddings() -> int | None:
        contados = servicio.embedding_service
        return contados.llamadas if isinstance(contados, EmbeddingsContados) else None

    def contar(modo_cola: ModoCola, antes_de: datetime | None) -> Awaitable[int]:
        return contar_pendientes(engine, modo_cola, antes_de)

    try:
        if modo == "frecuente":
            return await vaciar_frecuente(
                args,
                servicio,
                contar=contar,
                preparar_destino=lambda: preparar_destino(engine, qdrant),
                fijar_intentos=fijar_intentos,
                peticiones=lambda: cliente.peticiones,
                embeddings=embeddings,
            )
        return await sincronizar(
            args,
            servicio,
            contar=contar,
            preparar_destino=lambda: preparar_destino(engine, qdrant),
            aplicar_anexos=lambda listas: aplicar_documentos_oficiales(engine, listas),
            fijar_intentos=fijar_intentos,
            peticiones=lambda: cliente.peticiones,
            embeddings=embeddings,
            purgar=servicio.purgar_cola
            if utc_now_naive().weekday() == DIA_RETENCION
            else None,
        )
    finally:
        await engine.dispose()
        await qdrant.close()


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    p.add_argument(
        "--modo",
        choices=["auto", "nocturna", "frecuente"],
        default="auto",
        help=(
            "nocturna: lista por tramos, vacía y reintenta; frecuente: solo vacía "
            f"la cola; auto: nocturna a las {HORA_NOCTURNA_UTC}:00 UTC"
        ),
    )
    p.add_argument(
        "--limite",
        type=int,
        default=None,
        help="tope de items crudos por tramo (MERCADOPUBLICO_FETCHING_LIMIT)",
    )
    p.add_argument(
        "--estado",
        default=TENDER_STATUSES["PUBLISHED"],
        help="filtro de estado en el servidor; vacío para no filtrar",
    )
    p.add_argument(
        "--tramo-horas",
        type=float,
        default=TRAMO_HORAS,
        help=f"tamaño de cada tramo de la red de seguridad ({TRAMO_HORAS:g})",
    )
    p.add_argument(
        "--max-peticiones",
        type=int,
        default=None,
        help="tope de peticiones a Mercado Público de la corrida (sin tope)",
    )
    p.add_argument(
        "--sin-marcar",
        action="store_true",
        help="obsoleta, sin efecto: el barrido de vencidas lo hace sync_estados",
    )
    p.add_argument(
        "--confirmar-produccion",
        action="store_true",
        help="requerido si la base no es local",
    )
    p.add_argument(
        "--forzar",
        action="store_true",
        help="cerrar cualquier corrida en 'running' y correr igual",
    )
    p.add_argument(
        "--timeout-minutos",
        type=float,
        default=None,
        help=(
            f"tope de la corrida ({DEFAULT_TIMEOUT_MINUTOS} la nocturna, "
            f"{TIMEOUT_FRECUENTE_MINUTOS} la frecuente)"
        ),
    )
    return p


def main() -> None:
    args = construir_parser().parse_args()
    modo = args.modo if args.modo != "auto" else elegir_modo(utc_now_naive())

    print(f"Base de datos : {settings.database_url.split('@')[-1]}")
    print(f"Embeddings    : {settings.embedding_provider}")
    print(f"Modo          : {modo}\n")

    mensaje = verificar_destino(
        settings.database_url, confirmar_produccion=args.confirmar_produccion
    )
    if mensaje:
        print(mensaje, file=sys.stderr)
        sys.exit(2)

    frecuente = modo == "frecuente"
    minutos = args.timeout_minutos or (
        TIMEOUT_FRECUENTE_MINUTOS if frecuente else DEFAULT_TIMEOUT_MINUTOS
    )
    sys.exit(
        asyncio.run(
            con_timeout(
                _correr(args, modo),
                segundos=minutos * 60,
                codigo_al_vencer=0 if frecuente else 1,
            )
        )
    )


if __name__ == "__main__":
    main()
