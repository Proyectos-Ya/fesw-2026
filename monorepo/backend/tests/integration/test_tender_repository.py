from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.tender_repository import TenderFilters
from app.infrastructure.repositories.tender_model import (
    BuyerInstitutionModel,
    RegionModel,
    TenderModel,
    TenderStatusModel,
)
from app.infrastructure.repositories.tender_repository import TenderRepository
from app.shared.constants import CHILE_REGIONS

# `db_session` y el esquema limpio los aporta tests/integration/conftest.py,
# que apunta a la base de test y no a la de desarrollo.


def utc_now_naive() -> datetime:
    """Returns a timezone-naive UTC datetime to avoid Python 3.12 deprecations and DB offset issues."""
    return datetime.now(UTC).replace(tzinfo=None)


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
    region = RegionModel(id=13, name=CHILE_REGIONS[13])
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
    assert results[0].region == CHILE_REGIONS[13]


@pytest.mark.asyncio
async def test_get_tenders_filter_by_region(db_session: AsyncSession):
    repo = TenderRepository(db_session)

    # Seed regions
    r1 = RegionModel(id=13, name=CHILE_REGIONS[13])
    r2 = RegionModel(id=5, name=CHILE_REGIONS[5])
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
    filters = TenderFilters(regions=[CHILE_REGIONS[13]])
    results = await repo.get_tenders(filters)
    assert len(results) == 1
    assert results[0].code == "COT-METRO"
    assert results[0].region == CHILE_REGIONS[13]


@pytest.mark.asyncio
async def test_get_tenders_filter_by_province(db_session: AsyncSession):
    """Prueba el mecanismo del filtro, no que sirva con datos reales.

    Siembra `province` a mano porque la ingesta la escribe siempre como None: el
    dato no existe en la API de Compra Ágil. Contra la base real este filtro
    devuelve siempre cero resultados (PENDIENTES.md 6.17).

    Es el mismo patrón que mantuvo invisible el bug de numeración de regiones —un
    test que crea datos que la ingesta nunca produce—, así que queda dicho en vez
    de dar la impresión de que la funcionalidad está cubierta.
    """
    repo = TenderRepository(db_session)

    # Seed region
    region = RegionModel(id=13, name=CHILE_REGIONS[13])
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
