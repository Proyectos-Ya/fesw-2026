"""Sincronización diaria de licitaciones, para correr como cron aislado.

Qué resuelve
------------
El scheduler que hay hoy vive dentro del proceso de la API (`main.py`, dentro del
`lifespan`). Eso obliga al contenedor a un solo worker —dos duplicarían la
ingesta—, mete ~50 minutos diarios de CPU y red en el mismo proceso que atiende a
los usuarios, y sondea la base cada 2 segundos aunque no haya nada que hacer
(43.200 consultas al día). Sacado a un cron, las tres cosas desaparecen.

Y, sobre todo, **usa el cursor**. `ingestion_run`, `ventana_a_sincronizar()`,
`registrar_inicio()` y `registrar_fin()` estaban implementados y probados desde
la ingesta de septiembre, pero **sin ningún llamador en producción**: el
scheduler sigue pidiendo "las últimas 24 h contadas desde ahora". Con un proceso
siempre vivo eso casi nunca falla; con un cron sí, porque una ejecución que no
corre deja un hueco que nadie vuelve a mirar. Este script es el que cierra ese
circuito.

Qué hace, en orden
------------------
1. **Marca las vencidas.** Cuota cero: `closing_at` ya está en Postgres. Va
   primero porque es lo que libera cupos del pre-filtrado, y porque conviene que
   ocurra aunque la API esté caída.
2. **Lista lo publicado en la ventana que dice el cursor** y encola lo que falte.
3. **Vacía la cola**, bajando el detalle de cada licitación nueva.
4. **Cierra la corrida** en `ingestion_run`. Solo `ok` mueve el cursor: una
   corrida que no alcanzó a listar su ventana entera queda `partial`, y la
   siguiente vuelve a pedir el tramo que faltó.

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
    python -m scripts.sync_diaria --limite 100                  # prueba local
    python -m scripts.sync_diaria --confirmar-produccion        # lo que ejecuta el cron
    python -m scripts.sync_diaria --sin-marcar                  # solo la sincronización

Dos protecciones para correr sin supervisión:

- **Se niega contra una base que no sea local** salvo `--confirmar-produccion`.
  Una prueba local con un `.env` que quedó apuntando a producción escribía ahí sin
  avisar; el servicio de Railway lleva el flag en su `startCommand`.
- **Timeout duro** (`--timeout-minutos`, 120 por defecto). Railway no termina una
  corrida colgada y **omite todas las siguientes**, así que un cron que se queda
  esperando deja de correr para siempre. Al vencer sale con código 1; la fila de
  `ingestion_run` queda en `running`, que nunca mueve el cursor.

Códigos de salida: 0 si la ventana se listó entera; 1 si quedó a medias o venció
el timeout; 2 si se negó a correr contra una base no local. En un cron de Railway
ese código es la única señal visible de que algo salió mal.
"""

import argparse
import asyncio
import sys
import time
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any
from urllib.parse import urlsplit

from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.services.tender_ingestion_service import ITenderIngestionService
from app.application.use_cases.mark_expired_tenders import MarkExpiredTendersUseCase
from app.config import settings
from app.infrastructure.repositories.qdrant_tender_repository import (
    QdrantTenderRepository,
)
from app.infrastructure.repositories.tender_repository import TenderRepository
from app.shared.constants import TENDER_STATUSES
from scripts.ingesta_compartida import (
    construir_servicio,
    contar_pendientes,
    es_local,
    preparar_destino,
    vaciar_cola,
)

# Una corrida de un día hábil tarda ~50 minutos (4.500 detalles a ~3,3 s con
# concurrencia 5). El doble deja margen para una API lenta sin dejar que una
# corrida colgada bloquee la del día siguiente.
DEFAULT_TIMEOUT_MINUTOS = 120


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


async def con_timeout(corutina: Coroutine[Any, Any, int], segundos: float) -> int:
    """Corre la sincronización con un tope de tiempo, y la da por fallida al vencer.

    `asyncio.wait_for` cancela la corrida, y el `finally` de `_correr` alcanza a
    cerrar el engine y el cliente de Qdrant: el proceso termina de verdad, que es
    lo que Railway necesita para lanzar la ejecución siguiente.
    """
    try:
        return await asyncio.wait_for(corutina, timeout=segundos)
    except TimeoutError:
        print(
            f"\nERROR: la corrida superó el tope de {segundos / 60:.0f} min y se "
            "canceló.\nLa fila de ingestion_run queda en 'running', que no mueve "
            "el cursor: la corrida siguiente vuelve a pedir la misma ventana."
        )
        return 1


async def _marcar_vencidas(engine: AsyncEngine, qdrant: AsyncQdrantClient) -> int:
    """Pasa a `cerrada` lo que venció y sigue figurando publicado.

    Se marcan y **no se borran** del índice: el buscador expone un filtro por
    estado que acepta `cerrada`, y borrando el punto esa búsqueda devolvería cero
    para siempre. El cupo del pre-filtrado se libera igual, porque ese filtra por
    `status_code` del payload.
    """
    async with AsyncSession(engine) as session:
        caso = MarkExpiredTendersUseCase(
            repository=TenderRepository(session),
            tender_vector_repo=QdrantTenderRepository(
                client=qdrant, vector_size=settings.embedding_vector_size
            ),
        )
        return await caso.execute()


async def sincronizar(
    args: argparse.Namespace,
    servicio: ITenderIngestionService,
    *,
    contar: Callable[[], Awaitable[int]],
    marcar_vencidas: Callable[[], Awaitable[int]],
    preparar_destino: Callable[[], Awaitable[None]] | None = None,
) -> int:
    """Orquesta la corrida y devuelve el código de salida.

    Recibe sus colaboradores en vez de construirlos: lo que decide si la corrida
    es `ok` o `partial` —y con eso, si el cursor avanza— es lógica que conviene
    poder probar sin levantar Postgres ni Qdrant.
    """
    inicio = time.perf_counter()

    if preparar_destino is not None:
        await preparar_destino()

    if not args.sin_marcar:
        print(f"--- Vencidas marcadas como cerradas: {await marcar_vencidas()} ---")

    desde, hasta = await servicio.ventana_a_sincronizar()
    print(f"--- Ventana: {desde.isoformat()} → {hasta.isoformat()} ---")

    run_id = await servicio.registrar_inicio(desde, hasta)
    limite = args.limite or settings.mercadopublico_fetching_limit

    # `por_publicacion=True` y no la ventana de cambios: descubrir licitaciones
    # nuevas preguntando "qué se publicó en este rango" es correcto por
    # construcción. La alternativa —`ttl_cambio_ms`— **asume** que publicarse
    # cuenta como un cambio, y si esa suposición fuera falsa el cron no
    # descubriría nada nuevo sin que nada fallara. Medido el 2026-09-10 sobre el
    # listado real, la suposición se sostiene (`fecha_publicacion` y
    # `fecha_ultimo_cambio` de una licitación recién publicada están a un minuto
    # una de otra), pero no hay razón para depender de ella.
    listado = await servicio.fetch_tenders_metadata(
        desde=desde,
        hasta=hasta,
        por_publicacion=True,
        estado=args.estado or None,
        limite=limite,
    )
    print(
        f"{listado.listadas} licitaciones listadas, {listado.nuevas} nuevas encoladas."
    )

    if listado.listadas >= limite:
        print(
            f"\nAVISO: se listaron exactamente {limite}, que es el techo de la\n"
            "corrida. Quedaron licitaciones sin mirar, la corrida se registra\n"
            "como 'partial' y el cursor NO avanza — así que la sincronización\n"
            "no va a progresar hasta que se suba MERCADOPUBLICO_FETCHING_LIMIT\n"
            "por encima del volumen real (medido: ~5.600 cambios publicados\n"
            "en un día hábil)."
        )
    elif not listado.completo:
        print(
            "\nAVISO: el listado quedó incompleto (la API cortó la paginación).\n"
            "La corrida se registra como 'partial' y la siguiente vuelve a\n"
            "pedir el tramo que faltó."
        )

    resultado = await vaciar_cola(servicio, contar)
    print(
        f"{resultado.procesadas} procesadas en {resultado.rondas} rondas, "
        f"{resultado.pendientes} pendientes."
    )

    if resultado.cuota_agotada:
        print(
            "\nAVISO: se agotó la cuota diaria del ticket. Lo encolado no se\n"
            "pierde: la corrida siguiente lo retoma desde la cola."
        )
    elif resultado.sin_avance:
        print(
            "\nAVISO: varias rondas seguidas sin avanzar. Hay licitaciones que\n"
            "fallan de forma reproducible; revisa `tender_metadata.last_error`."
        )

    # `ok` significa **que se listó la ventana entera**, no que se procesara todo.
    # Son cosas distintas a propósito: una vez que los códigos están en
    # `tender_metadata` ya no se pierden, y el detalle pendiente lo retoma la
    # corrida siguiente desde la cola. Lo que no se puede perder es un tramo de la
    # ventana sin listar, y eso es justo lo que marca `partial`.
    estado = "ok" if listado.completo else "partial"
    await servicio.registrar_fin(
        run_id,
        status=estado,
        listed=listado.listadas,
        processed=resultado.procesadas,
        failed=resultado.pendientes,
    )

    print(f"\nCorrida '{estado}' en {(time.perf_counter() - inicio) / 60:.1f} min.")
    return 0 if estado == "ok" else 1


async def _correr(args: argparse.Namespace) -> int:
    """Arma las piezas reales y garantiza que el proceso cierre lo que abrió.

    Railway omite la ejecución siguiente de un cron si la anterior sigue viva, así
    que dejar el engine o el cliente de Qdrant abiertos no es un descuido estético:
    es una sincronización que deja de correr.
    """
    servicio, engine, qdrant = construir_servicio()
    try:
        return await sincronizar(
            args,
            servicio,
            contar=lambda: contar_pendientes(engine),
            marcar_vencidas=lambda: _marcar_vencidas(engine, qdrant),
            preparar_destino=lambda: preparar_destino(engine, qdrant),
        )
    finally:
        await engine.dispose()
        await qdrant.close()


def main() -> None:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    p.add_argument(
        "--limite",
        type=int,
        default=None,
        help="tope de items crudos de la corrida (MERCADOPUBLICO_FETCHING_LIMIT)",
    )
    p.add_argument(
        "--estado",
        default=TENDER_STATUSES["PUBLISHED"],
        help="filtro de estado en el servidor; vacío para no filtrar",
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
        default=DEFAULT_TIMEOUT_MINUTOS,
        help=f"tope de la corrida ({DEFAULT_TIMEOUT_MINUTOS})",
    )
    args = p.parse_args()

    print(f"Base de datos : {settings.database_url.split('@')[-1]}")
    print(f"Embeddings    : {settings.embedding_provider}\n")

    mensaje = verificar_destino(
        settings.database_url, confirmar_produccion=args.confirmar_produccion
    )
    if mensaje:
        print(mensaje, file=sys.stderr)
        sys.exit(2)

    sys.exit(
        asyncio.run(con_timeout(_correr(args), segundos=args.timeout_minutos * 60))
    )


if __name__ == "__main__":
    main()
