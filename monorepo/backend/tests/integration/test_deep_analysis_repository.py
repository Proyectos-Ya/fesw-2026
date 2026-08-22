from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.entities.deep_analysis import DeepAnalysis
from app.infrastructure.repositories.supplier_model import SupplierModel
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
    """Retorna datetime UTC naive para consistencia."""
    return datetime.now(UTC).replace(tzinfo=None)


async def seed_related_entities(
    session: AsyncSession, tender_id: UUID, supplier_id: UUID
):
    """Inserta las entidades necesarias en la base de datos para poder referenciar claves foráneas."""
    region = RegionModel(id=13, name=CHILE_REGIONS[13])
    session.add(region)

    status = TenderStatusModel(id=1, code="publicada", name="Publicada")
    session.add(status)

    buyer = BuyerInstitutionModel(
        rut="12.345.678-9",
        name="Municipalidad de Santiago",
        region_id=13,
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    session.add(buyer)

    supplier = SupplierModel(
        id=supplier_id,
        rut="12.345.678-9",
        legal_name="Empresa Ejemplo SpA",
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    session.add(supplier)

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
async def test_get_deep_analysis_not_found(db_session: AsyncSession):
    """Verifica que get_deep_analysis retorne None si no existe registro en la base de datos."""
    repo = TenderRepository(db_session)
    tender_id = uuid4()
    supplier_id = uuid4()

    result = await repo.get_deep_analysis(tender_id, supplier_id)
    assert result is None


@pytest.mark.asyncio
async def test_save_and_get_deep_analysis(db_session: AsyncSession):
    """Verifica que se pueda guardar un análisis nuevo mediante save_deep_analysis y recuperarlo con get_deep_analysis."""
    repo = TenderRepository(db_session)
    tender_id = uuid4()
    supplier_id = uuid4()
    await seed_related_entities(db_session, tender_id, supplier_id)

    analysis = DeepAnalysis(
        tender_id=tender_id,
        supplier_id=supplier_id,
        compatibility_score=85.0,
        recommendation="Postular",
        justification="Cumple con todos los requisitos técnicos.",
        prompt_instruction="Priorizar la cercanía geográfica",
    )

    # Guardar
    saved = await repo.save_deep_analysis(analysis)
    assert saved.id == analysis.id
    assert saved.compatibility_score == 85.0
    assert saved.recommendation == "Postular"
    assert saved.justification == "Cumple con todos los requisitos técnicos."
    assert saved.prompt_instruction == "Priorizar la cercanía geográfica"

    # Recuperar
    retrieved = await repo.get_deep_analysis(tender_id, supplier_id)
    assert retrieved is not None
    assert retrieved.id == analysis.id
    assert retrieved.compatibility_score == 85.0
    assert retrieved.recommendation == "Postular"
    assert retrieved.justification == "Cumple con todos los requisitos técnicos."
    assert retrieved.prompt_instruction == "Priorizar la cercanía geográfica"


@pytest.mark.asyncio
async def test_save_deep_analysis_updates_existing(db_session: AsyncSession):
    """Verifica que al volver a guardar un análisis para el mismo par (tender, supplier), actualice el registro existente sin violar restricciones de unicidad."""
    repo = TenderRepository(db_session)
    tender_id = uuid4()
    supplier_id = uuid4()
    await seed_related_entities(db_session, tender_id, supplier_id)

    # Primer guardado
    analysis_1 = DeepAnalysis(
        tender_id=tender_id,
        supplier_id=supplier_id,
        compatibility_score=85.0,
        recommendation="Postular",
        justification="Cumple con todos los requisitos técnicos.",
        prompt_instruction="Priorizar la cercanía geográfica",
    )
    await repo.save_deep_analysis(analysis_1)

    # Segundo guardado (actualización)
    analysis_2 = DeepAnalysis(
        tender_id=tender_id,
        supplier_id=supplier_id,
        compatibility_score=92.5,
        recommendation="Postular",
        justification="Se agregaron nuevas certificaciones que aumentan compatibilidad.",
        prompt_instruction="Priorizar la cercanía geográfica e ISO 9001",
    )

    # Debe actualizar el registro existente en lugar de intentar insertar un nuevo registro con el mismo (tender_id, supplier_id)
    updated = await repo.save_deep_analysis(analysis_2)

    assert updated.compatibility_score == 92.5
    assert (
        updated.justification
        == "Se agregaron nuevas certificaciones que aumentan compatibilidad."
    )
    assert updated.prompt_instruction == "Priorizar la cercanía geográfica e ISO 9001"

    # Validamos que en la BD siga habiendo un solo registro
    retrieved = await repo.get_deep_analysis(tender_id, supplier_id)
    assert retrieved is not None
    assert retrieved.compatibility_score == 92.5
    assert (
        retrieved.justification
        == "Se agregaron nuevas certificaciones que aumentan compatibilidad."
    )
