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
from sqlalchemy import Boolean, DateTime, Double, Integer, Text, inspect, text
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


async def test_tender_guarda_las_cotizaciones_y_su_fecha_de_revision(engine_migrado):
    """Plan HU-30: tres columnas nullable y sin default.

    Sin default, para que agregarlas no reescriba la tabla y la versión anterior
    de la app, que no las conoce, siga insertando filas durante el deploy.
    """

    def _columnas(connection):
        return {c["name"]: c for c in inspect(connection).get_columns("tender")}

    async with engine_migrado.connect() as conn:
        columnas = await conn.run_sync(_columnas)

    ofertas = columnas["received_offers_count"]
    revision = columnas["offers_checked_at"]
    primer_llamado = columnas["first_call_offers_count"]
    assert isinstance(ofertas["type"], Integer)
    assert isinstance(primer_llamado["type"], Integer)
    # Naive, como el resto de las fechas de `tender`.
    assert isinstance(revision["type"], DateTime) and not revision["type"].timezone
    for columna in (ofertas, revision, primer_llamado):
        assert columna["nullable"] is True
        assert columna["default"] is None


async def test_tender_guarda_la_entrega_y_los_requisitos(engine_migrado):
    """Plan #294: cuatro columnas nullable y sin default.

    `NULL` es que el detalle no lo informó. En los flags, `false` es un dato.
    """

    def _columnas(connection):
        return {c["name"]: c for c in inspect(connection).get_columns("tender")}

    async with engine_migrado.connect() as conn:
        columnas = await conn.run_sync(_columnas)

    direccion = columnas["delivery_address"]
    plazo = columnas["delivery_term_days"]
    medioambientales = columnas["requires_environmental_criteria"]
    impacto_social = columnas["requires_social_impact_criteria"]
    assert isinstance(direccion["type"], Text)
    assert isinstance(plazo["type"], Integer)
    assert isinstance(medioambientales["type"], Boolean)
    assert isinstance(impacto_social["type"], Boolean)
    for columna in (direccion, plazo, medioambientales, impacto_social):
        assert columna["nullable"] is True
        assert columna["default"] is None


async def test_tender_guarda_la_ubicacion_de_la_entrega(engine_migrado):
    """Plan #314: cuatro columnas nullable y sin default, y la cola indexada.

    `delivery_geocoded_at` nulo es "pendiente de geocodificar". El índice
    parcial cubre solo esa fracción de la tabla.
    """

    def _leer(connection):
        inspector = inspect(connection)
        columnas = {c["name"]: c for c in inspector.get_columns("tender")}
        indices = {i["name"]: i for i in inspector.get_indexes("tender")}
        return columnas, indices

    async with engine_migrado.connect() as conn:
        columnas, indices = await conn.run_sync(_leer)
        definicion = await conn.scalar(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE indexname = 'ix_tender_geocodificacion_pendiente'"
            )
        )

    lat = columnas["delivery_lat"]
    lng = columnas["delivery_lng"]
    precision = columnas["delivery_geo_precision"]
    geocodificada = columnas["delivery_geocoded_at"]
    assert isinstance(lat["type"], Double)
    assert isinstance(lng["type"], Double)
    assert isinstance(precision["type"], Text)
    assert isinstance(geocodificada["type"], DateTime)
    assert not geocodificada["type"].timezone
    for columna in (lat, lng, precision, geocodificada):
        assert columna["nullable"] is True
        assert columna["default"] is None

    assert "ix_tender_geocodificacion_pendiente" in indices
    assert "delivery_address IS NOT NULL" in definicion
    assert "delivery_geocoded_at IS NULL" in definicion


async def test_la_cache_de_geocodificacion_guarda_tambien_los_no_encontrados(
    engine_migrado,
):
    """Plan #314: `lat`/`lng` nulos = Nominatim no encontró la consulta."""

    def _leer(connection):
        inspector = inspect(connection)
        columnas = {c["name"]: c for c in inspector.get_columns("geocoding_cache")}
        pk = inspector.get_pk_constraint("geocoding_cache")
        return columnas, pk

    async with engine_migrado.connect() as conn:
        columnas, pk = await conn.run_sync(_leer)

    assert pk["constrained_columns"] == ["query"]
    assert isinstance(columnas["query"]["type"], Text)
    assert columnas["lat"]["nullable"] is True
    assert columnas["lng"]["nullable"] is True
    assert isinstance(columnas["lat"]["type"], Double)
    assert columnas["geocoded_at"]["nullable"] is False
