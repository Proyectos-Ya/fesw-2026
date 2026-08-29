"""Ejecuta SQL contra la base configurada. Sustituto de `psql` cuando no está.

    python -m scripts.sql "SELECT count(*) FROM tender"
    python -m scripts.sql -f consulta.sql

La conexión sale de `settings.database_url`, así que respeta DATABASE_URL igual
que el resto de las herramientas del proyecto.
"""

import argparse
import asyncio
import sys

import asyncpg
from sqlalchemy.engine import make_url

from app.config import settings


def _dsn() -> str:
    """DSN para asyncpg: sin el `+asyncpg` que entiende SQLAlchemy y él no."""
    url = make_url(settings.database_url)
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


async def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("sql", nargs="?", help="sentencia a ejecutar")
    p.add_argument("-f", "--archivo", help="leer la sentencia de un archivo")
    args = p.parse_args()

    if args.archivo:
        sentencia = open(args.archivo).read()
    elif args.sql:
        sentencia = args.sql
    else:
        sentencia = sys.stdin.read()

    conn = await asyncpg.connect(_dsn())
    try:
        if sentencia.strip().lower().startswith("select"):
            for fila in await conn.fetch(sentencia):
                print("  ".join(f"{k}={v}" for k, v in fila.items()))
        else:
            print(await conn.execute(sentencia))
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
