"""Las migraciones de Alembic tienen que reflejar exactamente los modelos.

Es el equivalente de `alembic check` dentro de la suite: aplica **todas las
migraciones** sobre una base vacía y la compara contra el metadata de los
modelos. Si difieren, o falta una migración o un modelo no describe lo que la
migración creó.

Por qué la base es propia y no la de `conftest`: esa se arma con
`SQLModel.metadata.create_all`, o sea desde los mismos modelos, y compararla
contra ellos no puede fallar nunca. La primera versión de este test hacía eso, y
por eso no vio que la migración de membresías (`f1e2d3c4b5a6`) creaba
`ON DELETE CASCADE` y `server_default` que los modelos no declaraban
(PENDIENTES 3.29): el siguiente `--autogenerate` los habría borrado.
"""

import os
import subprocess
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel

import app.infrastructure.repositories.models  # noqa: F401  (registra los modelos)
from app.config import settings

pytestmark = pytest.mark.integration

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_BASE_URL = make_url(settings.database_url)
_DB_MIGRADA = f"{_BASE_URL.database}_migraciones"


def _url_for(database: str) -> str:
    return _BASE_URL.set(database=database).render_as_string(hide_password=False)


async def _recrear_base(nombre: str) -> None:
    """Deja la base vacía. `FORCE` corta conexiones que hayan quedado colgadas."""
    admin = create_async_engine(_url_for("postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            # El nombre sale de la configuración, no de entrada de usuario.
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)'))
            await conn.execute(text(f'CREATE DATABASE "{nombre}"'))
    finally:
        await admin.dispose()


def _migrar(url: str) -> None:
    """`alembic upgrade head` contra `url`, en un proceso aparte.

    `env.py` toma la URL de `settings.database_url` y corre su propio
    `asyncio.run`, así que no puede llamarse desde dentro de un test async.
    """
    resultado = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": url},
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert resultado.returncode == 0, (
        f"alembic upgrade head falló:\n{resultado.stdout}\n{resultado.stderr}"
    )


@pytest_asyncio.fixture
async def engine_migrado() -> AsyncGenerator[AsyncEngine, None]:
    try:
        await _recrear_base(_DB_MIGRADA)
    except (OSError, SQLAlchemyError) as exc:
        pytest.skip(
            f"Postgres no está disponible en {_BASE_URL.host}:{_BASE_URL.port}: "
            f"{type(exc).__name__}"
        )
    _migrar(_url_for(_DB_MIGRADA))
    engine = create_async_engine(_url_for(_DB_MIGRADA))
    try:
        yield engine
    finally:
        await engine.dispose()


async def test_el_esquema_migrado_coincide_con_los_modelos(engine_migrado):
    def _comparar(connection):
        # Las mismas opciones que `env.py`, para ver lo mismo que `alembic check`.
        contexto = MigrationContext.configure(
            connection,
            opts={"compare_type": True, "compare_server_default": True},
        )
        return compare_metadata(contexto, SQLModel.metadata)

    async with engine_migrado.connect() as conn:
        diferencias = await conn.run_sync(_comparar)

    assert not diferencias, (
        "Las migraciones y los modelos no coinciden. Si cambiaste un modelo, genera "
        "la migración (`alembic revision --autogenerate`); si la migración ya está "
        "aplicada, ajusta el modelo a lo que creó.\n"
        f"Diferencias: {diferencias}"
    )
