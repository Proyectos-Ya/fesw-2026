"""Retención de licitaciones cerradas que nadie usó (plan 306).

Una licitación se borra si no está activa, cerró antes del corte y no tiene
filas en ninguna tabla de uso. Con ella se van sus partidas, sus resultados de
matching, sus notificaciones y todo lo que cuelga con CASCADE.

Las filas de uso se insertan con las claves foráneas apagadas
(`session_replication_role = replica`) y valores de relleno en las columnas
obligatorias. Así cada tabla de uso tiene su caso sin sembrar usuarios,
empresas y sesiones de chat para cada una. El borrado corre con las claves
foráneas encendidas, que es lo que se prueba.
"""

import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.repositories.sql_tender_retention_repository import (
    TABLAS_DE_USO,
    TABLAS_DEL_SISTEMA_EN_CASCADA,
    TABLAS_DEL_SISTEMA_SIN_CASCADA,
    SqlTenderRetentionRepository,
)
from app.infrastructure.repositories.tender_model import (
    BuyerInstitutionModel,
    TenderItemModel,
    TenderModel,
)
from app.infrastructure.seeder import seed_database_metadata
from app.shared.datetime_utils import utc_now_naive

pytestmark = pytest.mark.asyncio

AHORA = utc_now_naive()
CORTE = AHORA - timedelta(days=7)
VIEJA = AHORA - timedelta(days=10)
RECIENTE = AHORA - timedelta(days=2)
PUBLICADA, CERRADA, DESIERTA = 2, 3, 6


@pytest_asyncio.fixture
async def repo(integration_engine: AsyncEngine) -> SqlTenderRetentionRepository:
    async with AsyncSession(integration_engine) as s:
        await seed_database_metadata(s)
        s.add(
            BuyerInstitutionModel(
                rut="1-9",
                name="Comprador",
                region_id=13,
                created_at=AHORA,
                updated_at=AHORA,
            )
        )
        await s.commit()
    return SqlTenderRetentionRepository(integration_engine)


async def _licitacion(
    engine: AsyncEngine,
    *,
    status_id: int = CERRADA,
    closing_at: datetime = VIEJA,
    partidas: int = 2,
) -> uuid.UUID:
    tender_id = uuid.uuid4()
    async with AsyncSession(engine) as s:
        s.add(
            TenderModel(
                id=tender_id,
                code=f"C-{tender_id.hex[:8]}",
                name="Licitación",
                status_id=status_id,
                published_at=closing_at - timedelta(days=5),
                closing_at=closing_at,
                last_change_at=closing_at,
                buyer_rut="1-9",
                buyer_unit="Unidad",
                created_at=AHORA,
                updated_at=AHORA,
            )
        )
        await s.flush()
        for _ in range(partidas):
            s.add(
                TenderItemModel(
                    id=uuid.uuid4(),
                    tender_id=tender_id,
                    product_code="1",
                    name="Partida",
                    quantity=1,
                    unit_of_measure="u",
                )
            )
        await s.commit()
    return tender_id


_RELLENO_POR_TIPO = {
    "uuid": "gen_random_uuid()",
    "text": "'x'",
    "character varying": "'x'",
    "integer": "1",
    "bigint": "1",
    "smallint": "1",
    "numeric": "1",
    "double precision": "1",
    "real": "1",
    "boolean": "false",
    "timestamp without time zone": "now()",
    "timestamp with time zone": "now()",
    "date": "current_date",
    "json": "'{}'",
    "jsonb": "'{}'",
    "ARRAY": "'{}'",
}


async def _fila_en(engine: AsyncEngine, tabla: str, tender_id: uuid.UUID) -> None:
    """Una fila de `tabla` que apunta a la licitación, con relleno en lo obligatorio."""
    async with engine.begin() as conn:
        columnas = (
            await conn.execute(
                text(
                    """
                    SELECT column_name, data_type, udt_name
                      FROM information_schema.columns
                     WHERE table_schema = 'public' AND table_name = :tabla
                       AND is_nullable = 'NO' AND column_default IS NULL
                       AND is_identity = 'NO' AND column_name <> 'tender_id'
                    """
                ),
                {"tabla": tabla},
            )
        ).all()
        nombres = ["tender_id"]
        valores = [":tender_id"]
        for nombre, tipo, udt in columnas:
            nombres.append(f'"{nombre}"')
            if tipo == "USER-DEFINED":
                valores.append(
                    f"(SELECT enumlabel::{udt} FROM pg_enum e JOIN pg_type t"
                    f" ON t.oid = e.enumtypid WHERE t.typname = '{udt}' LIMIT 1)"
                )
            else:
                valores.append(_RELLENO_POR_TIPO[tipo])
        # El relleno no cumple los CHECK de cada tabla (estados, sha256). La
        # base de la suite se recrea en cada test, así que quitarlos es seguro.
        checks = (
            await conn.execute(
                text(
                    "SELECT conname FROM pg_constraint"
                    " WHERE contype = 'c' AND conrelid = CAST(:tabla AS regclass)"
                ),
                {"tabla": tabla},
            )
        ).scalars()
        for check in list(checks):
            await conn.execute(text(f'ALTER TABLE {tabla} DROP CONSTRAINT "{check}"'))
        await conn.execute(text("SET LOCAL session_replication_role = replica"))
        await conn.execute(
            text(
                f"INSERT INTO {tabla} ({', '.join(nombres)})"
                f" VALUES ({', '.join(valores)})"
            ),
            {"tender_id": tender_id},
        )


async def _existe(engine: AsyncEngine, tender_id: uuid.UUID) -> bool:
    async with engine.connect() as conn:
        return bool(
            await conn.scalar(
                text("SELECT count(*) FROM tender WHERE id = :id"), {"id": tender_id}
            )
        )


async def _filas(engine: AsyncEngine, tabla: str, tender_id: uuid.UUID) -> int:
    async with engine.connect() as conn:
        return await conn.scalar(
            text(f"SELECT count(*) FROM {tabla} WHERE tender_id = :id"),
            {"id": tender_id},
        )


async def test_cerrada_vieja_sin_uso_se_borra_con_lo_que_genero_el_sistema(
    repo, integration_engine
):
    tender_id = await _licitacion(integration_engine)
    for tabla in TABLAS_DEL_SISTEMA_SIN_CASCADA + TABLAS_DEL_SISTEMA_EN_CASCADA:
        if tabla != "tender_item":
            await _fila_en(integration_engine, tabla, tender_id)

    ids = await repo.ids_borrables(CORTE, limite=100)
    borradas = await repo.borrar(ids, CORTE)

    assert ids == [tender_id]
    assert borradas == 1
    assert not await _existe(integration_engine, tender_id)
    for tabla in TABLAS_DEL_SISTEMA_SIN_CASCADA + TABLAS_DEL_SISTEMA_EN_CASCADA:
        assert await _filas(integration_engine, tabla, tender_id) == 0, tabla


@pytest.mark.parametrize("tabla", TABLAS_DE_USO)
async def test_cerrada_vieja_con_uso_se_conserva(repo, integration_engine, tabla):
    tender_id = await _licitacion(integration_engine)
    await _fila_en(integration_engine, tabla, tender_id)

    assert await repo.ids_borrables(CORTE, limite=100) == []
    assert await repo.borrar([tender_id], CORTE) == 0
    assert await _existe(integration_engine, tender_id)
    assert await _filas(integration_engine, "tender_item", tender_id) == 2


async def test_cerrada_reciente_se_conserva(repo, integration_engine):
    await _licitacion(integration_engine, closing_at=RECIENTE)

    assert await repo.ids_borrables(CORTE, limite=100) == []


async def test_publicada_con_cierre_vencido_se_conserva(repo, integration_engine):
    """La cierra primero el barrido de vencidas; hasta entonces sigue activa."""
    tender_id = await _licitacion(integration_engine, status_id=PUBLICADA)

    assert await repo.ids_borrables(CORTE, limite=100) == []
    assert await repo.borrar([tender_id], CORTE) == 0


async def test_cualquier_estado_no_activo_es_borrable(repo, integration_engine):
    desierta = await _licitacion(integration_engine, status_id=DESIERTA)

    assert await repo.ids_borrables(CORTE, limite=100) == [desierta]


async def test_respeta_el_limite_y_entrega_primero_las_mas_viejas(
    repo, integration_engine
):
    mas_vieja = await _licitacion(
        integration_engine, closing_at=VIEJA - timedelta(days=5)
    )
    await _licitacion(integration_engine, closing_at=VIEJA)

    assert await repo.ids_borrables(CORTE, limite=1) == [mas_vieja]


async def test_uso_entre_la_seleccion_y_el_borrado_conserva_todo(
    repo, integration_engine
):
    """Si alguien la guarda después de `ids_borrables`, el borrado la salta y
    no le quita las partidas."""
    tender_id = await _licitacion(integration_engine)
    ids = await repo.ids_borrables(CORTE, limite=100)
    await _fila_en(integration_engine, "saved_tender", tender_id)

    assert await repo.borrar(ids, CORTE) == 0
    assert await _existe(integration_engine, tender_id)
    assert await _filas(integration_engine, "tender_item", tender_id) == 2


async def test_borrar_sin_ids_no_hace_nada(repo):
    assert await repo.borrar([], CORTE) == 0


async def test_toda_tabla_que_apunta_a_tender_esta_clasificada(
    repo, integration_engine
):
    """Una tabla nueva con clave foránea a `tender` obliga a decidir si cuenta
    como uso. Sin esto, una NO ACTION haría fallar el borrado y una CASCADE se
    llevaría datos de alguien sin que nadie lo decidiera."""
    async with integration_engine.connect() as conn:
        filas = (
            await conn.execute(
                text(
                    """
                    SELECT conrelid::regclass::text, confdeltype::text
                      FROM pg_constraint
                     WHERE contype = 'f' AND confrelid = 'tender'::regclass
                    """
                )
            )
        ).all()
    clasificadas = (
        set(TABLAS_DE_USO)
        | set(TABLAS_DEL_SISTEMA_SIN_CASCADA)
        | set(TABLAS_DEL_SISTEMA_EN_CASCADA)
    )
    sin_clasificar = {tabla for tabla, _ in filas} - clasificadas
    assert sin_clasificar == set()
    # Las del sistema sin cascada se borran a mano; si alguna pasara a CASCADE
    # o SET NULL, sobra en esa lista y conviene moverla.
    no_action = {tabla for tabla, regla in filas if regla == "a"}
    assert set(TABLAS_DEL_SISTEMA_SIN_CASCADA) <= no_action
