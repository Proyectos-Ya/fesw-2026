"""Carga inicial del corpus de licitaciones (PENDIENTES 6.1).

La ingesta normal solo pide una ventana de 24 h, así que un entorno nuevo arranca
vacío y tarda semanas en acumular catálogo. Este script pide una ventana ancha
una sola vez.

Dos fases, las mismas de la ingesta diaria:

1. **Listado** → encola códigos en `tender_metadata` (`is_processed=False`).
2. **Detalle** → por cada uno pide su ficha, calcula el embedding y escribe en
   Postgres (`tender`, `tender_item`, `buyer_institution`) y en la colección
   `tenders` de Qdrant.

Es **reanudable**: la fase 2 marca `is_processed` al terminar cada licitación, así
que una interrupción no pierde trabajo. Se retoma con `--reanudar`.

Uso
---
    # Diagnóstico: 1 petición, no escribe nada. Empieza siempre por aquí.
    python -m scripts.bootstrap_corpus --solo-contar --dias 30

    # Carga completa. `--limite` sale del total que reportó --solo-contar y es
    # obligatorio contra una base no local: sin él la carga se corta en
    # MERCADOPUBLICO_FETCHING_LIMIT (2000) y lo reporta como éxito.
    python -m scripts.bootstrap_corpus --dias 30 --limite 5000

    # Terminar lo que quedó pendiente tras una interrupción
    python -m scripts.bootstrap_corpus --reanudar

Advertencias
------------
- **La cuota es del ticket, no de la máquina.** Si tres personas corren esto son
  3×N peticiones sobre las mismas 10.000 del día. Lo corre una sola persona y
  comparte el resultado como dump.
- Apuntar a una base que no sea local exige `--confirmar-produccion`. Cargar
  contra producción desde una máquina de desarrollo es una operación deliberada,
  no algo que deba pasar por olvidar una variable de entorno.
"""

import argparse
import asyncio
import sys
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings
from app.infrastructure.repositories.tender_model import TenderMetadataModel
from app.infrastructure.services.tenders.mercado_publico_client import (
    MercadoPublicoClient,
)
from app.infrastructure.services.tenders.tender_ingestion_service import (
    TenderIngestionService,
)
from app.shared.constants import TENDER_STATUSES

HOSTS_LOCALES = {"localhost", "127.0.0.1", "::1", "host.docker.internal", "db"}


def _es_local(url: str) -> bool:
    return (urlsplit(url).hostname or "") in HOSTS_LOCALES


def _falta_limite_explicito(limite: int | None, es_local: bool) -> bool:
    """Si hay que abortar por no haber dicho cuántas licitaciones se quieren.

    Sin `--limite`, `fetch_tenders_metadata` cae en
    `MERCADOPUBLICO_FETCHING_LIMIT` (2000) y `get_tenders` corta la lista ahí.
    Un corpus mayor se carga a medias y el log lo reporta como éxito.

    Contra una base local da igual: la corrida se repite cuando se quiera. Contra
    producción no, porque la cuota es del ticket y son 10.000 peticiones al día
    para todo el equipo. Mismo criterio que `--confirmar-produccion`: lo caro e
    irreversible no puede depender de acordarse de un argumento.
    """
    return limite is None and not es_local


def _hay_riesgo_de_truncado(total: int, limite: int | None, tope: int) -> bool:
    """Si el techo efectivo se queda por debajo de lo que la API dice que hay.

    `total` viene de `total_resultados` del listado. Un 0 significa que no se
    pudo saber, no que no haya nada: en ese caso no se afirma nada.
    """
    if total <= 0:
        return False
    return total > (limite if limite is not None else tope)


def _construir_servicio() -> tuple[TenderIngestionService, object, AsyncQdrantClient]:
    """Arma el servicio de ingesta con las mismas piezas que usa la aplicación."""
    from app.bootstrap import build_embedding_service

    engine = create_async_engine(settings.database_url, echo=False)
    qdrant = AsyncQdrantClient(
        url=settings.qdrant_url, api_key=settings.qdrant_api_key
    )
    servicio = TenderIngestionService(
        engine=engine,
        client=MercadoPublicoClient(api_key=settings.mercado_publico_api_key),
        embedding_service=build_embedding_service(),
        qdrant_client=qdrant,
    )
    return servicio, engine, qdrant


async def _pendientes(engine) -> int:
    async with AsyncSession(engine) as s:
        stmt = (
            select(func.count())
            .select_from(TenderMetadataModel)
            .where(col(TenderMetadataModel.is_processed).is_(False))
        )
        return (await s.exec(stmt)).one()  # type: ignore[arg-type]


async def contar(args: argparse.Namespace) -> None:
    """Una petición al listado: cuántas hay y qué estados devuelve la API."""
    import httpx

    hasta = datetime.now(UTC)
    desde = hasta - timedelta(days=args.dias)
    params: dict[str, object] = {"tamano_pagina": 20, "numero_pagina": 1}
    if args.por_publicacion:
        params["publicado_desde"] = desde.strftime("%Y-%m-%dT%H:%M:%SZ")
        params["publicado_hasta"] = hasta.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        params["ttl_cambio_ms"] = int(args.dias * 24 * 3600 * 1000)
    if args.estado:
        params["estado"] = args.estado

    print(f"Consultando con: {params}\n")
    async with httpx.AsyncClient(timeout=90) as c:
        r = await c.get(
            "https://api2.mercadopublico.cl/v2/compra-agil",
            headers={"ticket": settings.mercado_publico_api_key},
            params=params,  # type: ignore[arg-type]
        )
    if r.status_code != 200:
        print(f"HTTP {r.status_code}: {r.text[:300]}")
        print("\nSi es 504, prueba una ventana más corta o quita el filtro de estado.")
        return

    payload = r.json().get("payload", {})
    pag = payload.get("paginacion", {})
    items = payload.get("items", [])
    total = pag.get("total_resultados", 0)

    print(f"total_resultados : {total}")
    print(f"total_paginas    : {pag.get('total_paginas')}")
    print("\nEstados en la primera página (id_estado | codigo):")
    from collections import Counter

    for (id_e, cod), n in Counter(
        (i.get("estado", {}).get("id_estado"), i.get("estado", {}).get("codigo"))
        for i in items
    ).most_common():
        print(f"  {str(id_e):>4} | {cod:<24} x{n}")

    # El detalle domina el tiempo: ~3,3 s por licitación, medido.
    horas = total * 3.3 / 3600
    print(
        f"\nEstimación para {total} licitaciones:"
        f"\n  peticiones : ~{total + total // 20} de las 10.000 diarias del ticket"
        f"\n  tiempo     : ~{horas:.1f} h (el detalle tarda ~3,3 s cada uno)"
    )

    tope = settings.mercadopublico_fetching_limit
    if _hay_riesgo_de_truncado(total, args.limite, tope):
        efectivo = args.limite if args.limite is not None else tope
        print(
            f"\nAVISO: el techo efectivo son {efectivo} licitaciones y la API dice"
            f" que hay {total}.\n"
            f"Sin --limite la carga se queda en {efectivo} y el log igual dirá que"
            " terminó bien.\n"
            f"Corre la carga con: --limite {total + total // 10}"
        )
    if total >= 10000:
        print(
            "\nAVISO: 10.000 es sospechosamente redondo y puede ser un tope de la\n"
            "API, no el total real. Acota la ventana para tener un número fiable."
        )


async def _preparar_destino(engine, qdrant) -> None:
    """Deja la base y el índice listos para recibir datos.

    Normalmente lo hace el arranque de la aplicación (`main.py`), pero contra un
    entorno recién creado la aplicación todavía no se ha ejecutado nunca: la
    tabla `region` estaría vacía y los FK de `tender` fallarían, y la colección
    `tenders` no existiría. Ambas operaciones son idempotentes.
    """
    from app.infrastructure.repositories.qdrant_tender_repository import (
        QdrantTenderRepository,
    )
    from app.infrastructure.seeder import seed_database_metadata

    async with AsyncSession(engine) as s:
        await seed_database_metadata(s)
    print("Regiones y estados sembrados.")

    await QdrantTenderRepository(
        client=qdrant, vector_size=settings.embedding_vector_size
    ).ensure_collection()
    print("Colección 'tenders' lista (con sus índices de payload).\n")


async def cargar(args: argparse.Namespace) -> None:
    servicio, engine, qdrant = _construir_servicio()
    try:
        await _preparar_destino(engine, qdrant)

        if not args.reanudar:
            print(f"--- Fase 1: listado ({args.dias} días) ---")
            t0 = time.perf_counter()
            nuevas = await servicio.fetch_tenders_metadata(
                dias=args.dias,
                por_publicacion=args.por_publicacion,
                estado=args.estado,
                limite=args.limite,
            )
            print(f"{nuevas} licitaciones encoladas en {time.perf_counter() - t0:.0f} s")
            techo = args.limite or settings.mercadopublico_fetching_limit
            if nuevas >= techo:
                print(
                    f"AVISO: se encolaron exactamente {nuevas}, que es el techo"
                    f" pedido. Es casi seguro que quedaron licitaciones fuera;"
                    f" vuelve a correr con un --limite mayor."
                )
            print()

        pendientes = await _pendientes(engine)
        print(f"--- Fase 2: detalle ({pendientes} pendientes) ---")
        if not pendientes:
            print("Nada que procesar.")
            return

        t0 = time.perf_counter()
        ronda = 0
        while pendientes:
            ronda += 1
            await servicio.process_unprocessed_tenders()
            restantes = await _pendientes(engine)
            if restantes == pendientes:
                # Sin avance: insistir solo repetiría el mismo fallo.
                print(
                    f"Ronda {ronda} no avanzó ({restantes} pendientes). Se detiene; "
                    "revisa los errores de más arriba y reanuda con --reanudar."
                )
                break
            hechas = pendientes - restantes
            pendientes = restantes
            print(f"  ronda {ronda}: {hechas} procesadas, quedan {restantes}")

        print(f"\nListo en {(time.perf_counter() - t0) / 60:.1f} min.")
    finally:
        await engine.dispose()
        await qdrant.close()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--dias", type=int, default=30, help="ancho de la ventana (30)")
    p.add_argument(
        "--estado",
        default=TENDER_STATUSES["PUBLISHED"],
        help="filtro de estado en el servidor; vacío para no filtrar",
    )
    p.add_argument(
        "--por-cambio",
        dest="por_publicacion",
        action="store_false",
        help="usar ttl_cambio_ms en vez de la fecha de publicación",
    )
    p.set_defaults(por_publicacion=True)
    p.add_argument("--limite", type=int, default=None, help="tope de items crudos")
    p.add_argument("--solo-contar", action="store_true", help="diagnóstico, no escribe")
    p.add_argument("--reanudar", action="store_true", help="saltar la fase 1")
    p.add_argument(
        "--confirmar-produccion",
        action="store_true",
        help="requerido si la base no es local",
    )
    args = p.parse_args()

    destino = urlsplit(settings.database_url).hostname
    print(f"Base de datos : {destino}")
    print(f"Qdrant        : {urlsplit(settings.qdrant_url).hostname}")
    print(f"Embeddings    : {settings.embedding_provider}\n")

    if not args.solo_contar and not _es_local(settings.database_url):
        if not args.confirmar_produccion:
            sys.exit(
                f"La base ({destino}) no es local y falta --confirmar-produccion.\n"
                "Cargar contra producción es deliberado, no algo que deba pasar por\n"
                "olvidar una variable de entorno."
            )
        if _falta_limite_explicito(args.limite, es_local=False):
            sys.exit(
                "Falta --limite y la base no es local.\n"
                f"Sin él la carga se corta en {settings.mercadopublico_fetching_limit}"
                " licitaciones y lo reporta como éxito.\n"
                "Corre primero el diagnóstico, que gasta una sola petición:\n"
                f"  python -m scripts.bootstrap_corpus --solo-contar --dias {args.dias}"
            )
        print("!! Cargando contra una base NO local !!\n")

    asyncio.run(contar(args) if args.solo_contar else cargar(args))


if __name__ == "__main__":
    main()
