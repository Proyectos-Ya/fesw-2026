"""El paso de datos de la migración que agrega el puntero de cambios a la cola.

Plan 305. Además de las columnas, la migración deja la cola de producción en el
estado del diseño nuevo:

- `detail_fetched_at` se rellena desde `tender.last_change_at`, que hasta ahora
  era el momento de la última bajada del detalle.
- Las compras cuyo detalle falla siempre (504 en la API y en la página oficial)
  pasan a estado terminal en vez de seguir gastando una ronda cada noche.
- Lo que sigue pendiente queda etiquetado: `nueva` si no está en `tender`,
  `actualizar` si ya está.

Corre las migraciones en una base propia, igual que `test_migraciones.py`: la de
`conftest` sale de los modelos y no tiene datos de antes de la migración.
"""

import os
import subprocess
import sys
from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import settings

pytestmark = pytest.mark.integration

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_BASE_URL = make_url(settings.database_url)
_DB = f"{_BASE_URL.database}_migracion_cola"
# La cabeza anterior a la migración del plan 305.
_ANTES = "1ddfcce953b7"

BAJADA_1 = datetime(2026, 10, 1, 12, 0)
BAJADA_2 = datetime(2026, 10, 2, 12, 0)
ERROR_504 = (
    "ErrorTransitorioMercadoPublico: HTTP 504 al pedir el detalle de P-504 "
    "tras 4 intentos."
)


def _url_for(database: str) -> str:
    return _BASE_URL.set(database=database).render_as_string(hide_password=False)


async def _recrear_base(nombre: str) -> None:
    admin = create_async_engine(_url_for("postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)'))
            await conn.execute(text(f'CREATE DATABASE "{nombre}"'))
    finally:
        await admin.dispose()


def _alembic(*args: str) -> None:
    resultado = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=_BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": _url_for(_DB)},
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert resultado.returncode == 0, (
        f"alembic {' '.join(args)} falló:\n{resultado.stdout}\n{resultado.stderr}"
    )


@pytest_asyncio.fixture
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    try:
        await _recrear_base(_DB)
    except (OSError, SQLAlchemyError) as exc:
        pytest.skip(
            f"Postgres no está disponible en {_BASE_URL.host}:{_BASE_URL.port}: "
            f"{type(exc).__name__}"
        )
    _alembic("upgrade", _ANTES)
    motor = create_async_engine(_url_for(_DB))
    try:
        yield motor
    finally:
        await motor.dispose()


async def _sembrar(engine: AsyncEngine) -> None:
    ahora = datetime(2026, 10, 12, 8, 0)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO region (id, name) VALUES (13, 'RM') ON CONFLICT DO NOTHING"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO tender_status (id, code, name) "
                "VALUES (2, 'publicada', 'Publicada') ON CONFLICT DO NOTHING"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO buyer_institution "
                "(rut, name, region_id, created_at, updated_at) "
                "VALUES ('1-9', 'Comprador', 13, :ahora, :ahora)"
            ),
            {"ahora": ahora},
        )
        for code, bajada in (("T-1", BAJADA_1), ("T-2", BAJADA_2)):
            await conn.execute(
                text(
                    "INSERT INTO tender (id, code, name, status_id, published_at, "
                    "closing_at, last_change_at, buyer_rut, buyer_unit, "
                    "created_at, updated_at) VALUES (:id, :code, 'Licitación', 2, "
                    ":ahora, :ahora, :bajada, '1-9', 'Unidad', :ahora, :ahora)"
                ),
                {"id": uuid4(), "code": code, "ahora": ahora, "bajada": bajada},
            )
        filas = (
            # Ya procesada.
            ("T-1", True, 0, None),
            # Reencolada por el cron de estados.
            ("T-2", False, 0, None),
            # Detalle que falla siempre: pasa a terminal.
            ("P-504", False, 14, ERROR_504),
            # Nueva con un solo fallo: sigue en la cola.
            ("P-NUEVA", False, 1, ERROR_504.replace("P-504", "P-NUEVA")),
            # Nueva sin intentos.
            ("P-SIN", False, 0, None),
        )
        for code, procesada, intentos, error in filas:
            await conn.execute(
                text(
                    "INSERT INTO tender_metadata (id, code, is_processed, attempts, "
                    "last_error, created_at, updated_at) VALUES (:id, :code, "
                    ":procesada, :intentos, :error, :ahora, :ahora)"
                ),
                {
                    "id": uuid4(),
                    "code": code,
                    "procesada": procesada,
                    "intentos": intentos,
                    "error": error,
                    "ahora": ahora,
                },
            )


async def _filas(engine: AsyncEngine) -> dict[str, dict]:
    async with engine.connect() as conn:
        resultado = await conn.execute(
            text(
                "SELECT code, pending_reason, detail_fetched_at, night_retries, "
                "discarded_at, discard_reason FROM tender_metadata"
            )
        )
        return {fila.code: dict(fila._mapping) for fila in resultado}


async def test_rellena_la_ultima_bajada_desde_tender(engine):
    await _sembrar(engine)
    _alembic("upgrade", "head")

    filas = await _filas(engine)

    assert filas["T-1"]["detail_fetched_at"] == BAJADA_1
    assert filas["T-2"]["detail_fetched_at"] == BAJADA_2
    assert filas["P-SIN"]["detail_fetched_at"] is None


async def test_pasa_a_terminal_las_que_fallan_siempre(engine):
    await _sembrar(engine)
    _alembic("upgrade", "head")

    filas = await _filas(engine)

    assert filas["P-504"]["discarded_at"] is not None
    assert filas["P-504"]["discard_reason"] == "reintentos_agotados"
    assert filas["P-504"]["pending_reason"] is None
    # Un solo fallo no basta para darla por perdida.
    assert filas["P-NUEVA"]["discarded_at"] is None


async def test_etiqueta_lo_que_sigue_pendiente(engine):
    await _sembrar(engine)
    _alembic("upgrade", "head")

    filas = await _filas(engine)

    assert filas["T-1"]["pending_reason"] is None
    assert filas["T-2"]["pending_reason"] == "actualizar"
    assert filas["P-NUEVA"]["pending_reason"] == "nueva"
    assert filas["P-SIN"]["pending_reason"] == "nueva"
    assert all(f["night_retries"] == 0 for f in filas.values())


async def test_se_puede_revertir(engine):
    await _sembrar(engine)
    _alembic("upgrade", "head")
    _alembic("downgrade", _ANTES)

    async with engine.connect() as conn:
        columnas = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'tender_metadata'"
            )
        )
        nombres = {c for (c,) in columnas}

    assert "pending_reason" not in nombres
    assert "discarded_at" not in nombres
