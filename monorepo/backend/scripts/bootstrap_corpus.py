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
    # Diagnóstico: 2 peticiones, no escribe nada. Empieza siempre por aquí.
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

from app.config import settings
from app.infrastructure.services.tenders.mercado_publico_client import (
    MercadoPublicoClient,
)
from app.shared.constants import TENDER_STATUSES
from scripts.ingesta_compartida import (
    construir_servicio,
    contar_pendientes,
    es_local,
    preparar_destino,
    vaciar_cola,
)


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


async def contar(args: argparse.Namespace) -> None:
    """Diagnóstico del listado: cuántas hay y qué estados devuelve la API.

    Dos peticiones de las 10.000 del ticket. La primera pide solo el total
    (`MercadoPublicoClient.contar`); la segunda trae una página para mirar los
    estados. Las dos pasan por el cliente a propósito: la versión anterior hacía
    el GET a mano y **sin reintentos**, así que un 504 pasajero —que esta API
    devuelve con frecuencia— dejaba el diagnóstico sin número y sin decir por qué.
    """
    from collections import Counter

    cliente = MercadoPublicoClient(api_keys=settings.mercado_publico_tickets)
    hasta = datetime.now(UTC)
    desde = hasta - timedelta(days=args.dias)
    ventana = {"por_publicacion": args.por_publicacion, "estado": args.estado or None}

    print(f"Ventana: {args.dias} días, {ventana}\n")

    total = await cliente.contar(desde, hasta, **ventana)
    if total is None:
        print(
            "No se pudo obtener el total: la API no respondió tras los reintentos.\n"
            "Si el error de fondo es un 504, prueba una ventana más corta o quita\n"
            "el filtro de estado."
        )
        return

    print(f"total_resultados : {total}")

    listado = await cliente.get_tenders(desde, hasta, 20, **ventana)
    print("\nEstados en la primera página (id_estado | codigo):")
    for (id_e, cod), n in Counter(
        (i.get("estado", {}).get("id_estado"), i.get("estado", {}).get("codigo"))
        for i in listado.items
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


async def cargar(args: argparse.Namespace) -> None:
    servicio, engine, qdrant = construir_servicio()
    try:
        await preparar_destino(engine, qdrant)

        if not args.reanudar:
            print(f"--- Fase 1: listado ({args.dias} días) ---")
            t0 = time.perf_counter()
            listado = await servicio.fetch_tenders_metadata(
                dias=args.dias,
                por_publicacion=args.por_publicacion,
                estado=args.estado,
                limite=args.limite,
            )
            nuevas = listado.nuevas
            print(
                f"{nuevas} licitaciones encoladas en {time.perf_counter() - t0:.0f} s"
            )
            if not listado.completo:
                print(
                    "AVISO: el listado quedó incompleto (la API cortó la paginación"
                    " o se llegó al tope). Quedaron licitaciones sin encolar."
                )
            techo = args.limite or settings.mercadopublico_fetching_limit
            if nuevas >= techo:
                print(
                    f"AVISO: se encolaron exactamente {nuevas}, que es el techo"
                    f" pedido. Es casi seguro que quedaron licitaciones fuera;"
                    f" vuelve a correr con un --limite mayor."
                )
            print()

        pendientes = await contar_pendientes(engine)
        print(f"--- Fase 2: detalle ({pendientes} pendientes) ---")
        if not pendientes:
            print("Nada que procesar.")
            return

        resultado = await vaciar_cola(servicio, lambda: contar_pendientes(engine))

        if resultado.cuota_agotada:
            print(
                f"\nCuota diaria agotada con {resultado.pendientes} licitaciones "
                "pendientes.\nRetoma mañana con --reanudar."
            )
        elif resultado.sin_avance:
            print(
                "\nVarias rondas seguidas sin avanzar. Se detiene; revisa los "
                "errores de más arriba y reanuda con --reanudar."
            )

        print(f"\nListo en {resultado.segundos / 60:.1f} min.")
    finally:
        await engine.dispose()
        await qdrant.close()


def main() -> None:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
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

    if not args.solo_contar and not es_local(settings.database_url):
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
