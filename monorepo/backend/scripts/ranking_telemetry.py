"""Corre a mano el ciclo de la telemetría del ranking (plan 233, decisión 8).

Qué resuelve
------------
El bucle del lifespan (`RankingTelemetryScheduler`) corre este mismo ciclo cada 6 h.
Este script sirve para dos cosas: un backfill después de una caída larga y la QA de
la métrica sin esperar a que el bucle despierte (el NDCG de hoy no se calcula hasta
mañana, salvo con `--incluir-hoy`).

Qué hace, en orden
------------------
1. **NDCG@10 diario.** Recalcula los últimos `--dias` días completos de Chile, por
   versión del modelo, con upsert: una interacción puede llegar hasta 7 días
   después de servido el ranking. Un día sin datos crudos no pisa su fila.
2. **Prioridad de anexos en sombra.** Toma el snapshot. Nadie la consume.
3. **Purga.** Borra impresiones, interacciones y snapshots de más de 90 días. Las
   métricas diarias se conservan.

Todo es idempotente: correrlo dos veces deja lo mismo (salvo un snapshot más de la
prioridad en sombra).

Uso
---
    python -m scripts.ranking_telemetry                          # local
    python -m scripts.ranking_telemetry --dias 30 --incluir-hoy
    python -m scripts.ranking_telemetry --confirmar-produccion   # base compartida

Códigos de salida: 0 si todo terminó; 1 si algún trabajo falló (los demás corren
igual); 2 si se negó a correr contra una base no local o `--dias` es inválido.
"""

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.use_cases.ranking_telemetry.run_ranking_telemetry_cycle import (
    RankingTelemetryCycleResult,
)
from app.config import settings
from app.infrastructure.db import crear_engine
from app.infrastructure.services.ranking_telemetry_jobs import (
    build_ranking_telemetry_cycle,
)
from scripts.sync_diaria import verificar_destino

# Más atrás de 90 días la purga ya borró lo crudo: recalcular no tendría con qué.
MAX_DIAS = 90


def validar_dias(dias: int) -> str | None:
    """El motivo para rechazar `--dias`, o `None` si sirve."""
    if not 1 <= dias <= MAX_DIAS:
        return (
            f"--dias tiene que estar entre 1 y {MAX_DIAS}: más atrás la purga de "
            "90 días ya borró lo crudo."
        )
    return None


async def correr(
    args: argparse.Namespace,
    ciclo: Callable[[], Awaitable[RankingTelemetryCycleResult]],
) -> int:
    """Corre el ciclo, imprime el resumen y devuelve el código de salida.

    Recibe el ciclo en vez de construirlo: así se prueba sin Postgres.
    """
    resultado = await ciclo()
    print(f"Métricas diarias escritas : {resultado.metrics_written}")
    print(f"Snapshots de prioridad    : {resultado.priority_snapshots}")
    if resultado.purged is not None:
        print(
            "Purgado (más de 90 días)  : "
            f"{resultado.purged.impressions} impresiones, "
            f"{resultado.purged.interactions} interacciones, "
            f"{resultado.purged.priority_snapshots} snapshots"
        )
    for fallo in resultado.failures:
        print(f"ERROR: {fallo}")
    return 1 if resultado.failures else 0


async def _correr(args: argparse.Namespace) -> int:
    engine = crear_engine()
    maker = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    try:
        return await correr(
            args,
            build_ranking_telemetry_cycle(
                maker, ndcg_days=args.dias, include_today=args.incluir_hoy
            ),
        )
    finally:
        await engine.dispose()


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    p.add_argument(
        "--dias",
        type=int,
        default=7,
        help=f"días completos de Chile a recalcular (7; máx. {MAX_DIAS})",
    )
    p.add_argument(
        "--incluir-hoy",
        action="store_true",
        help="calcula también el día en curso (útil para probar a mano)",
    )
    p.add_argument(
        "--confirmar-produccion",
        action="store_true",
        help="requerido si la base no es local",
    )
    return p


def main() -> None:
    args = construir_parser().parse_args()

    print(f"Base de datos : {settings.database_url.split('@')[-1]}\n")

    mensaje = validar_dias(args.dias) or verificar_destino(
        settings.database_url, confirmar_produccion=args.confirmar_produccion
    )
    if mensaje:
        print(mensaje, file=sys.stderr)
        sys.exit(2)

    sys.exit(asyncio.run(_correr(args)))


if __name__ == "__main__":
    main()
