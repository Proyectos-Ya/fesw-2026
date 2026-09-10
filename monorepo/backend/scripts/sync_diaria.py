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
2. **Lista la ventana que dice el cursor** y encola lo que falte.
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
    python -m scripts.sync_diaria                 # lo que ejecuta el cron
    python -m scripts.sync_diaria --limite 9000   # forzando el tope de la corrida
    python -m scripts.sync_diaria --sin-marcar    # solo la sincronización

Sale con código 0 si la ventana se listó entera, y 1 si no: en un cron de Railway
ese código es la única señal visible de que algo quedó a medias.
"""

import argparse
import asyncio
import sys
import time
from collections.abc import Awaitable, Callable

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
    vaciar_cola,
)


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
) -> int:
    """Orquesta la corrida y devuelve el código de salida.

    Recibe sus colaboradores en vez de construirlos: lo que decide si la corrida
    es `ok` o `partial` —y con eso, si el cursor avanza— es lógica que conviene
    poder probar sin levantar Postgres ni Qdrant.
    """
    inicio = time.perf_counter()

    if not args.sin_marcar:
        print(f"--- Vencidas marcadas como cerradas: {await marcar_vencidas()} ---")

    desde, hasta = await servicio.ventana_a_sincronizar()
    print(f"--- Ventana: {desde.isoformat()} → {hasta.isoformat()} ---")

    run_id = await servicio.registrar_inicio(desde, hasta)
    limite = args.limite or settings.mercadopublico_fetching_limit

    listado = await servicio.fetch_tenders_metadata(
        desde=desde, hasta=hasta, estado=args.estado or None, limite=limite
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
    args = p.parse_args()

    print(f"Base de datos : {settings.database_url.split('@')[-1]}")
    print(f"Embeddings    : {settings.embedding_provider}\n")

    sys.exit(asyncio.run(_correr(args)))


if __name__ == "__main__":
    main()
