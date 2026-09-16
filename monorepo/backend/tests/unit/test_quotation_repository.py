import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.entities.quotation import MaterialItem, QuotationInput
from app.infrastructure.repositories.quotation_repository import QuotationRepository


@pytest.mark.asyncio
async def test_migration_save_read_replace_and_company_isolation(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'quotation.db'}")
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/a227c0150001_cotizaciones_materiales.py"
    )
    spec = importlib.util.spec_from_file_location("quotation_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    def migrate(connection):
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()

    supplier, tender = uuid4(), uuid4()
    async with engine.begin() as connection:
        # Esquema mínimo previo; las tablas de la funcionalidad las crea Alembic.
        await connection.execute(
            text(
                "CREATE TABLE supplier (id CHAR(32) PRIMARY KEY, user_id CHAR(32), rut VARCHAR, legal_name VARCHAR, trade_name VARCHAR, description VARCHAR, regions JSON, sectors JSON, certifications JSON, keywords JSON, years_experience INTEGER, num_employees INTEGER, created_at DATETIME, updated_at DATETIME, profile_changed_at DATETIME)"
            )
        )
        await connection.execute(text("CREATE TABLE tender (id CHAR(32) PRIMARY KEY)"))
        await connection.execute(
            text("INSERT INTO supplier (id) VALUES (:id)"), {"id": supplier.hex}
        )
        await connection.execute(
            text("INSERT INTO tender (id) VALUES (:id)"), {"id": tender.hex}
        )
        await connection.run_sync(migrate)

    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            repo = QuotationRepository(session)
            data = QuotationInput(
                items=[
                    MaterialItem(
                        description="Cemento",
                        unit="saco",
                        quantity="2.5",
                        unit_price="100.25",
                    )
                ]
            )
            first = await repo.save(supplier, tender, data)
        async with AsyncSession(engine, expire_on_commit=False) as session:
            repo = QuotationRepository(session)
            retrieved = await repo.get(supplier, tender)
            assert retrieved.id == first.id
            assert str(retrieved.total) == "250.63"
            assert await repo.get(uuid4(), tender) is None
            updated = await repo.save(
                supplier,
                tender,
                QuotationInput(
                    currency="USD",
                    items=[
                        MaterialItem(
                            description="Arena", unit="m3", quantity="1", unit_price="0"
                        )
                    ],
                ),
            )
            assert updated.id == first.id
        async with AsyncSession(engine) as session:
            retrieved = await QuotationRepository(session).get(supplier, tender)
            assert retrieved.currency == "USD"
            assert [item.description for item in retrieved.items] == ["Arena"]
            assert retrieved.total == 0
            assert (
            await session.exec(text("SELECT count(*) FROM quotation"))
            ).scalar() == 1
            assert (
            await session.exec(text("SELECT count(*) FROM quotation_material"))
            ).scalar() == 1
    finally:
        await engine.dispose()
