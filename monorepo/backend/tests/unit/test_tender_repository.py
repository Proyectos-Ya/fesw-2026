from datetime import datetime, timezone
from typing import AsyncGenerator
from uuid import uuid4, UUID
import pytest
import pytest_asyncio
from sqlmodel import delete
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.entities.tender import Tender
from app.application.repositories.tender_repository import TenderFilters
from app.infrastructure.db import engine, SQLModel
from app.infrastructure.repositories.tender_model import (
    TenderModel,
    BuyerInstitutionModel,
    TenderStatusModel,
    RegionModel,
)
from app.infrastructure.repositories.supplier_model import SupplierModel
from app.infrastructure.repositories.tender_repository import TenderRepository



def utc_now_naive() -> datetime:
    """Returns a timezone-naive UTC datetime to avoid Python 3.12 deprecations and DB offset issues."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Fixture que crea automáticamente todas las tablas antes de ejecutar cada prueba
@pytest_asyncio.fixture(autouse=True)
async def setup_db_tables():
    # Asegura que todas las tablas estén creadas en la base de datos
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield


# Fixture para manejar la sesión de la base de datos y limpiar las tablas al finalizar la prueba
@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(engine) as session:
        yield session
        # Limpieza de tablas para evitar interferencias entre pruebas
        await session.exec(delete(TenderModel))
        await session.exec(delete(BuyerInstitutionModel))
        await session.exec(delete(TenderStatusModel))
        await session.exec(delete(RegionModel))
        await session.exec(delete(SupplierModel))
        await session.commit()

    
    # Libera los recursos del pool de conexiones para evitar problemas de event loop de asyncio
    await engine.dispose()



@pytest.mark.asyncio
async def test_get_tenders_empty(db_session: AsyncSession):
    repo = TenderRepository(db_session)
    filters = TenderFilters()
    tenders = await repo.get_tenders(filters)
    assert tenders == []


@pytest.mark.asyncio
async def test_get_by_id(db_session: AsyncSession):
    repo = TenderRepository(db_session)

    # 1. Seed region
    region = RegionModel(id=13, name="Metropolitana")
    db_session.add(region)

    # 2. Seed status
    status = TenderStatusModel(id=1, code="publicada", name="Publicada")
    db_session.add(status)

    # 3. Seed buyer institution
    buyer = BuyerInstitutionModel(
        rut="12.345.678-9",
        name="Municipalidad de Santiago",
        region_id=13,
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    db_session.add(buyer)
    await db_session.commit()

    # 4. Create and save tender model directly
    tender_id = uuid4()
    tender_model = TenderModel(
        id=tender_id,
        code="1057539-228-COT26",
        name="Materiales Eléctricos",
        description="Compra de cables y enchufes",
        status_id=1,
        published_at=utc_now_naive(),
        closing_at=utc_now_naive(),
        last_change_at=utc_now_naive(),
        buyer_rut="12.345.678-9",
        buyer_unit="Operaciones",
        province="Santiago",
        available_amount_clp=500000.0,
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    db_session.add(tender_model)
    await db_session.commit()

    # 5. Retrieve using filter by id
    filters = TenderFilters(ids=[tender_id])
    results = await repo.get_tenders(filters)
    assert len(results) == 1
    assert results[0].id == tender_id
    assert results[0].name == "Materiales Eléctricos"


@pytest.mark.asyncio
async def test_get_tenders_filter_by_region(db_session: AsyncSession):
    repo = TenderRepository(db_session)

    # Seed regions
    r1 = RegionModel(id=13, name="Metropolitana")
    r2 = RegionModel(id=5, name="Valparaíso")
    db_session.add(r1)
    db_session.add(r2)

    # Seed status
    status = TenderStatusModel(id=1, code="publicada", name="Publicada")
    db_session.add(status)

    # Seed buyers
    b1 = BuyerInstitutionModel(
        rut="11.111.111-1",
        name="Municipalidad de Santiago",
        region_id=13,
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    b2 = BuyerInstitutionModel(
        rut="22.222.222-2",
        name="Municipalidad de Valparaíso",
        region_id=5,
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    db_session.add(b1)
    db_session.add(b2)
    await db_session.commit()

    # Create tenders directly
    t1 = TenderModel(
        id=uuid4(),
        code="COT-METRO",
        name="Tender Metro",
        status_id=1,
        published_at=utc_now_naive(),
        closing_at=utc_now_naive(),
        last_change_at=utc_now_naive(),
        buyer_rut="11.111.111-1",
        buyer_unit="IT",
        province="Santiago",
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    t2 = TenderModel(
        id=uuid4(),
        code="COT-VALPO",
        name="Tender Valpo",
        status_id=1,
        published_at=utc_now_naive(),
        closing_at=utc_now_naive(),
        last_change_at=utc_now_naive(),
        buyer_rut="22.222.222-2",
        buyer_unit="IT",
        province="Valparaíso",
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    db_session.add(t1)
    db_session.add(t2)
    await db_session.commit()

    # Filter by region
    filters = TenderFilters(regions=["Metropolitana"])
    results = await repo.get_tenders(filters)
    assert len(results) == 1
    assert results[0].code == "COT-METRO"


@pytest.mark.asyncio
async def test_get_tenders_filter_by_province(db_session: AsyncSession):
    repo = TenderRepository(db_session)

    # Seed region
    region = RegionModel(id=13, name="Metropolitana")
    db_session.add(region)

    # Seed status
    status = TenderStatusModel(id=1, code="publicada", name="Publicada")
    db_session.add(status)

    # Seed buyer
    buyer = BuyerInstitutionModel(
        rut="12.345.678-9",
        name="Comprador Regional",
        region_id=13,
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    db_session.add(buyer)
    await db_session.commit()

    # Create tenders with different provinces
    t1 = TenderModel(
        id=uuid4(),
        code="T1",
        name="Tender 1",
        status_id=1,
        published_at=utc_now_naive(),
        closing_at=utc_now_naive(),
        last_change_at=utc_now_naive(),
        buyer_rut="12.345.678-9",
        buyer_unit="Operations",
        province="Santiago",
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    t2 = TenderModel(
        id=uuid4(),
        code="T2",
        name="Tender 2",
        status_id=1,
        published_at=utc_now_naive(),
        closing_at=utc_now_naive(),
        last_change_at=utc_now_naive(),
        buyer_rut="12.345.678-9",
        buyer_unit="Operations",
        province="Chacabuco",
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    db_session.add(t1)
    db_session.add(t2)
    await db_session.commit()

    # Filter by province
    filters = TenderFilters(provinces=["Chacabuco"])
    results = await repo.get_tenders(filters)
    assert len(results) == 1
    assert results[0].code == "T2"
