"""Entorno de Alembic.

La URL de conexión sale de `app.config.settings` y no de `alembic.ini`: así hay
una sola fuente de verdad y las credenciales no quedan en un archivo versionado.

`target_metadata` apunta al metadata de SQLModel, pero eso solo se puebla si los
módulos de modelos están importados: SQLModel los registra al definirlos. De ahí
el import de `app.infrastructure.repositories.models`; sin él, `--autogenerate`
no vería ninguna tabla y generaría una migración que borra el esquema entero.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel

import app.infrastructure.repositories.models  # noqa: F401  (registra los modelos)
from alembic import context
from app.config import settings
from app.infrastructure.db import _connect_args

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = SQLModel.metadata


def _configurar_y_migrar(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Sin esto, un cambio de tipo (por ejemplo varchar -> text) pasa
        # inadvertido en --autogenerate.
        compare_type=True,
        # Detecta también altas y bajas de valores por defecto del servidor.
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse, para revisarlo o aplicarlo a mano."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        # Mismos ajustes de asyncpg que usa la app: detrás de un pooler en modo
        # transacción (Supavisor 6543) las sentencias preparadas fallan de forma
        # intermitente, y una migración a medio aplicar es peor que una que no
        # parte. Sin esto, DB_DISABLE_PREPARED_STATEMENTS no llegaba a Alembic.
        connect_args=_connect_args(),
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_configurar_y_migrar)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
