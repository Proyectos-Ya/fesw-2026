"""Backfill: resuelve comuna para `buyer_institution` ya existentes.

Contexto
--------
`get_or_create_buyer` solo resuelve comuna (path "a": nombre de municipalidad,
ver `app/shared/comunas.py`) al **crear** un organismo — es un get-or-create
puro, así que un buyer que ya existía antes de esta feature (o que se creó sin
comuna porque su nombre no matcheaba en ese momento) nunca la gana de forma
automática. Este script aplica la misma heurística, una vez, sobre lo que ya
está en base.

No dispara ningún camino caro (barrido de Licitaciones v1, geocoding — no
implementados todavía, ver PENDIENTES.md 6.19). Es idempotente: solo toca
filas con `comuna_id IS NULL`, y nunca pisa una comuna ya resuelta.

Uso
---
    python -m scripts.backfill_buyer_comuna --dry-run   # muestra sin escribir
    python -m scripts.backfill_buyer_comuna             # aplica
"""

import argparse
import asyncio
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.shared.comunas import resolve_comuna_from_organismo_name

_SELECT_SIN_COMUNA = text("""
    SELECT rut, name FROM buyer_institution WHERE comuna_id IS NULL
""")

_SELECT_COMUNA_ID_BY_NAME = text("SELECT id FROM comuna WHERE name = :name")

_UPDATE_BUYER = text("""
    UPDATE buyer_institution
    SET comuna_id = :comuna_id, comuna_resolution_source = 'organismo_name'
    WHERE rut = :rut
""")


@dataclass
class Stats:
    sin_comuna: int = 0
    resueltos: int = 0
    no_reconocidos: list[str] = field(default_factory=list)


async def run(dry_run: bool) -> Stats:
    stats = Stats()
    engine = create_async_engine(settings.database_url)

    try:
        async with engine.connect() as conn:
            filas = (await conn.execute(_SELECT_SIN_COMUNA)).all()
        stats.sin_comuna = len(filas)
        if not filas:
            return stats

        for fila in filas:
            comuna_name = resolve_comuna_from_organismo_name(fila.name)
            if not comuna_name:
                stats.no_reconocidos.append(fila.name)
                continue

            async with engine.connect() as conn:
                comuna_id = (
                    await conn.execute(_SELECT_COMUNA_ID_BY_NAME, {"name": comuna_name})
                ).scalar()

            if comuna_id is None:
                stats.no_reconocidos.append(fila.name)
                continue

            stats.resueltos += 1
            if dry_run:
                print(
                    f"  [dry-run] {fila.rut} ({fila.name!r}) -> comuna_id={comuna_id}"
                )
                continue

            async with engine.begin() as conn:
                await conn.execute(
                    _UPDATE_BUYER, {"comuna_id": comuna_id, "rut": fila.rut}
                )
    finally:
        await engine.dispose()

    return stats


def _report(stats: Stats, dry_run: bool) -> None:
    modo = "DRY-RUN (no se escribió nada)" if dry_run else "APLICADO"
    print(f"\n=== Backfill de comuna del comprador — {modo} ===")
    print(f"  organismos sin comuna : {stats.sin_comuna}")
    print(f"  resueltos             : {stats.resueltos}")
    print(f"  sin reconocer         : {len(stats.no_reconocidos)}")

    if stats.no_reconocidos:
        muestra = ", ".join(stats.no_reconocidos[:10])
        resto = (
            ""
            if len(stats.no_reconocidos) <= 10
            else f" (+{len(stats.no_reconocidos) - 10})"
        )
        print(f"    {muestra}{resto}")
        print("    → no son municipalidades reconocibles; quedan solo con región")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra qué organismos se resolverían, sin escribir en la base.",
    )
    args = parser.parse_args()

    stats = asyncio.run(run(dry_run=args.dry_run))
    _report(stats, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
