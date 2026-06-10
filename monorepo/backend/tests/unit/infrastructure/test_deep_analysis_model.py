from datetime import datetime, timezone
from typing import AsyncGenerator
from uuid import uuid4
import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlmodel import delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.db import engine, SQLModel
from app.infrastructure.repositories.tender_model import (
    TenderModel,
    BuyerInstitutionModel,
    TenderStatusModel,
    RegionModel,
)
from app.infrastructure.repositories.supplier_model import SupplierModel
from app.infrastructure.repositories.deep_analysis_model import DeepAnalysisModel


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest_asyncio.fixture(autouse=True)
async def setup_db_tables():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(engine) as session:
        yield session
        await session.exec(delete(DeepAnalysisModel))
        await session.exec(delete(SupplierModel))
        await session.exec(delete(TenderModel))
        await session.exec(delete(BuyerInstitutionModel))
        await session.exec(delete(TenderStatusModel))
        await session.exec(delete(RegionModel))
        await session.commit()
    await engine.dispose()


async def seed_related_entities(session: AsyncSession, tender_id, supplier_id):
    """Crea y persiste las entidades relacionadas (Region, Status, Buyer, Supplier, Tender) necesarias para probar DeepAnalysisModel."""
    # 1. Seed region
    region = RegionModel(id=13, name="Metropolitana")
    session.add(region)

    # 2. Seed status
    status = TenderStatusModel(id=1, code="publicada", name="Publicada")
    session.add(status)

    # 3. Seed buyer institution
    buyer = BuyerInstitutionModel(
        rut="12.345.678-9",
        name="Municipalidad de Santiago",
        region_id=13,
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    session.add(buyer)

    # 4. Seed Supplier
    supplier = SupplierModel(
        id=supplier_id,
        rut="12.345.678-9",
        legal_name="Empresa Ejemplo SpA",
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    session.add(supplier)

    # 5. Seed Tender
    tender = TenderModel(
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
    session.add(tender)
    await session.commit()


@pytest.mark.asyncio
async def test_persist_and_retrieve_deep_analysis_model(db_session: AsyncSession):
    """Verifica que el modelo DeepAnalysisModel se pueda persistir correctamente en la base de datos y luego ser recuperado con todos sus datos íntegros."""
    tender_id = uuid4()
    supplier_id = uuid4()
    await seed_related_entities(db_session, tender_id, supplier_id)

    analysis_id = uuid4()
    analysis_model = DeepAnalysisModel(
        id=analysis_id,
        tender_id=tender_id,
        supplier_id=supplier_id,
        compatibility_score=88.5,
        recommendation="Postular",
        justification="Excelente alineación con el perfil del proveedor.",
        prompt_instruction="Ignora cables de red",
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    db_session.add(analysis_model)
    await db_session.commit()

    # Query back
    result = await db_session.exec(select(DeepAnalysisModel).where(DeepAnalysisModel.id == analysis_id))
    retrieved = result.one()

    assert retrieved.id == analysis_id
    assert retrieved.tender_id == tender_id
    assert retrieved.supplier_id == supplier_id
    assert retrieved.compatibility_score == 88.5
    assert retrieved.recommendation == "Postular"
    assert retrieved.justification == "Excelente alineación con el perfil del proveedor."
    assert retrieved.prompt_instruction == "Ignora cables de red"
    assert isinstance(retrieved.created_at, datetime)
    assert isinstance(retrieved.updated_at, datetime)


@pytest.mark.asyncio
async def test_composite_unique_constraint_raises(db_session: AsyncSession):
    """Verifica que la restricción de unicidad compuesta funcione: no se puede crear más de un análisis para el mismo par (tender_id, supplier_id)."""
    tender_id = uuid4()
    supplier_id = uuid4()
    await seed_related_entities(db_session, tender_id, supplier_id)

    analysis_1 = DeepAnalysisModel(
        id=uuid4(),
        tender_id=tender_id,
        supplier_id=supplier_id,
        compatibility_score=80.0,
        recommendation="Postular",
        justification="Primer intento",
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    db_session.add(analysis_1)
    await db_session.commit()

    analysis_2 = DeepAnalysisModel(
        id=uuid4(),
        tender_id=tender_id,
        supplier_id=supplier_id,
        compatibility_score=75.0,
        recommendation="Evaluar con cautela",
        justification="Segundo intento duplicado",
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    db_session.add(analysis_2)

    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

