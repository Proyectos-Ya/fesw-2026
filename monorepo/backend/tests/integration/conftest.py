"""Fixtures de los tests de integración: Postgres real, base de datos dedicada.

Estos tests recrean el esquema (`drop_all` + `create_all`) y borran filas. Contra
el engine de la aplicación eso **destruye la base de desarrollo**: no solo vacía
tablas, las elimina. Y como borra Postgres sin tocar Qdrant, deja los vectores
huérfanos, que es justo el desbalance que `rank_tenders` tiene que limpiar después.

Por eso apuntan a `<postgres_db>_test`, que este módulo crea si no existe. Si
Postgres no está levantado los tests se **saltan** en vez de fallar: un error de
disponibilidad de infraestructura no debe parecer un defecto del código.
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings

# Deriva el nombre de la base de test del de desarrollo, para que un `.env` que
# apunte a otra instancia siga aislando en la misma instancia.
TEST_DB_NAME = f"{settings.postgres_db}_test"

_SKIP_REASON = (
    f"Postgres no está disponible en {settings.postgres_host}:{settings.postgres_port}. "
    "Levántalo desde monorepo/ con `docker compose up -d postgres` para correr los "
    "tests de integración."
)


def _url_for(database: str) -> str:
    return (
        f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{database}"
    )


async def _ensure_test_database() -> None:
    """Crea la base de test si falta.

    `CREATE DATABASE` no puede ir dentro de una transacción, de ahí el
    AUTOCOMMIT. Se conecta a `postgres`, la base de mantención que siempre existe.
    """
    admin_engine = create_async_engine(
        _url_for("postgres"), isolation_level="AUTOCOMMIT"
    )
    try:
        async with admin_engine.connect() as conn:
            found = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": TEST_DB_NAME},
            )
            if found.scalar() is None:
                # El nombre sale de la configuración, no de entrada de usuario, y
                # va entre comillas dobles porque CREATE DATABASE no acepta
                # parámetros ligados.
                await conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    finally:
        await admin_engine.dispose()


@pytest_asyncio.fixture
async def integration_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Engine contra la base de test. Salta el test si Postgres no responde."""
    try:
        await _ensure_test_database()
    except (OSError, SQLAlchemyError) as exc:
        pytest.skip(f"{_SKIP_REASON}\nDetalle: {type(exc).__name__}")

    engine = create_async_engine(_url_for(TEST_DB_NAME), pool_pre_ping=True)
    try:
        yield engine
    finally:
        # Libera el pool para que no queden conexiones atadas al event loop del test.
        await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def setup_db_tables(
    integration_engine: AsyncEngine,
) -> AsyncGenerator[None, None]:
    """Esquema limpio antes de cada test.

    Al recrear las tablas, cada test parte de cero sin necesidad de borrar filas
    al terminar. Es seguro porque la base es exclusiva de la suite.
    """
    async with integration_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def db_session(
    integration_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(integration_engine) as session:
        yield session


def pytest_collection_modifyitems(items) -> None:
    """Marca todo lo de este directorio como `integration`.

    Permite excluirlos sin Postgres con `pytest -m "not integration"`.
    """
    for item in items:
        if "tests/integration/" in str(item.path).replace("\\", "/"):
            item.add_marker(pytest.mark.integration)
