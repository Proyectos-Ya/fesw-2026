"""Migración puntual: `tender.published_at` / `tender.closing_at` a UTC.

Contexto
--------
Estas dos columnas venían de la API de Mercado Público, que entrega la hora
local de Chile sin offset, y se guardaban tal cual. El resto de las fechas del
sistema (`created_at`, `updated_at`, `last_change_at`, `generated_at`) siempre
se guardó en UTC, así que la base quedó con dos zonas horarias mezcladas en
columnas del mismo tipo.

Desde el commit que introduce `app/shared/datetime_utils`, la ingesta normaliza
estas fechas a UTC en el borde de entrada. Este script corrige las filas que se
guardaron *antes* de ese cambio; las nuevas ya llegan correctas.

El proyecto no usa Alembic (las tablas se crean con `SQLModel.metadata.create_all`),
por eso la corrección va como script y no como migración versionada.

Uso
---
    python -m scripts.migrate_tender_dates_to_utc --dry-run   # previsualizar
    python -m scripts.migrate_tender_dates_to_utc             # aplicar

IMPORTANTE: no es idempotente. Correrlo dos veces desplaza las fechas dos veces.
Para evitarlo, deja una marca en la tabla `schema_migration_log` y se niega a
repetir la migración si ya está registrada (usar `--force` para ignorarlo, solo
si sabes lo que haces). Haz un respaldo de la base antes de ejecutar.
"""

import argparse
import asyncio
from datetime import datetime

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.db import engine
from app.shared.datetime_utils import to_utc_naive, utc_now_naive

MIGRATION_NAME = "tender_dates_to_utc"

_CREATE_LOG_TABLE = text(
    """
    CREATE TABLE IF NOT EXISTS schema_migration_log (
        name TEXT PRIMARY KEY,
        applied_at TIMESTAMP NOT NULL
    )
    """
)
_ALREADY_APPLIED = text("SELECT 1 FROM schema_migration_log WHERE name = :name")
_MARK_APPLIED = text(
    "INSERT INTO schema_migration_log (name, applied_at) VALUES (:name, :applied_at)"
)
_SELECT_TENDERS = text("SELECT id, code, published_at, closing_at FROM tender")
_UPDATE_TENDER = text(
    "UPDATE tender SET published_at = :published_at, closing_at = :closing_at WHERE id = :id"
)


async def migrate(dry_run: bool, force: bool) -> int:
    """Devuelve la cantidad de filas corregidas (o que se corregirían)."""
    async with AsyncSession(engine) as session:
        await session.execute(_CREATE_LOG_TABLE)

        applied = (
            await session.execute(_ALREADY_APPLIED, {"name": MIGRATION_NAME})
        ).first()
        if applied and not force:
            print(
                f"[Migración] '{MIGRATION_NAME}' ya fue aplicada. "
                "No se hace nada (usa --force para repetirla)."
            )
            return 0

        rows = (await session.execute(_SELECT_TENDERS)).all()
        print(f"[Migración] {len(rows)} licitaciones encontradas.")

        updated = 0
        for row in rows:
            published_utc = to_utc_naive(row.published_at)
            closing_utc = to_utc_naive(row.closing_at)
            if published_utc == row.published_at and closing_utc == row.closing_at:
                continue

            print(
                f"  {row.code}: publicación {_fmt(row.published_at)} → {_fmt(published_utc)} | "
                f"cierre {_fmt(row.closing_at)} → {_fmt(closing_utc)}"
            )
            if not dry_run:
                await session.execute(
                    _UPDATE_TENDER,
                    {
                        "id": row.id,
                        "published_at": published_utc,
                        "closing_at": closing_utc,
                    },
                )
            updated += 1

        if dry_run:
            print(
                f"[Migración] DRY RUN: se corregirían {updated} filas. Nada fue escrito."
            )
            return updated

        await session.execute(
            _MARK_APPLIED, {"name": MIGRATION_NAME, "applied_at": utc_now_naive()}
        )
        await session.commit()
        print(f"[Migración] Listo: {updated} filas corregidas.")
        return updated


def _fmt(value: datetime | None) -> str:
    return value.isoformat(sep=" ", timespec="minutes") if value else "—"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra los cambios sin escribir en la base.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ejecuta aunque la migración ya esté registrada.",
    )
    args = parser.parse_args()
    asyncio.run(migrate(dry_run=args.dry_run, force=args.force))


if __name__ == "__main__":
    main()
