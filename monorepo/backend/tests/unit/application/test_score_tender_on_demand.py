"""Pruebas del cálculo de compatibilidad pedido por el usuario.

Cubre lo que distingue a este camino del ranking: funciona sobre cualquier
licitación abierta (no solo el top-N), persiste el resultado y se niega a
calcular una licitación cerrada.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.application.services.compatibility_scorer import CompatibilityScorer
from app.application.use_cases.matching.score_tender_on_demand import (
    ScoreTenderOnDemandUseCase,
)
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender
from app.domain.errors.supplier_errors import SupplierNotFoundForUser
from app.domain.errors.tender_errors import TenderClosedForScoring, TenderNotFound
from app.shared.constants import TENDER_STATUSES
from tests.unit.application.fakes import (
    FakeRerankerService,
    FakeWeightingService,
    InMemoryMatchingResultRepository,
    InMemorySupplierRepository,
    InMemoryTenderRepository,
)


def crear_licitacion(
    tender_id: UUID,
    cierra_en_horas: int = 48,
    status_code: str = TENDER_STATUSES["PUBLISHED"],
) -> Tender:
    ahora = datetime.now(UTC).replace(tzinfo=None)
    return Tender(
        id=tender_id,
        code=f"COT-{tender_id}",
        name="Servicio de aseo",
        description="Aseo de oficinas",
        status_id=1,
        status_code=status_code,
        published_at=ahora - timedelta(days=1),
        closing_at=ahora + timedelta(hours=cierra_en_horas),
        last_change_at=ahora,
        buyer_rut="12.345.678-9",
        buyer_name="Municipalidad de Santiago",
        buyer_unit="TI",
        items=[],
    )


async def armar_caso() -> tuple[
    ScoreTenderOnDemandUseCase,
    InMemorySupplierRepository,
    InMemoryTenderRepository,
    InMemoryMatchingResultRepository,
    Supplier,
]:
    supplier_repo = InMemorySupplierRepository()
    supplier = Supplier(rut="76086428-5", legal_name="Empresa SpA", user_id=uuid4())
    await supplier_repo.save(supplier)

    tender_repo = InMemoryTenderRepository()
    matching_result_repo = InMemoryMatchingResultRepository()
    use_case = ScoreTenderOnDemandUseCase(
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        scorer=CompatibilityScorer(
            reranker_service=FakeRerankerService(),
            weighting_service=FakeWeightingService(),
            matching_result_repo=matching_result_repo,
        ),
    )
    return use_case, supplier_repo, tender_repo, matching_result_repo, supplier


@pytest.mark.asyncio
async def test_calcula_y_persiste_una_licitacion_fuera_del_top() -> None:
    use_case, _, tender_repo, matching_result_repo, supplier = await armar_caso()
    tender_id = uuid4()
    tender_repo.tenders[tender_id] = crear_licitacion(tender_id)

    resultado = await use_case.execute(
        user_id=supplier.user_id, tender_id=tender_id
    )

    assert resultado.source == "on_demand"
    assert 0.0 <= resultado.final_score <= 1.0
    guardado = await matching_result_repo.get_by_proveedor_and_licitacion(
        supplier.id, tender_id
    )
    assert guardado is not None


@pytest.mark.asyncio
async def test_recalcular_reemplaza_el_valor_anterior() -> None:
    use_case, _, tender_repo, matching_result_repo, supplier = await armar_caso()
    tender_id = uuid4()
    tender_repo.tenders[tender_id] = crear_licitacion(tender_id)

    await use_case.execute(user_id=supplier.user_id, tender_id=tender_id)
    await use_case.execute(user_id=supplier.user_id, tender_id=tender_id)

    assert len(await matching_result_repo.get_by_supplier_id(supplier.id)) == 1


@pytest.mark.asyncio
async def test_sin_proveedor_falla() -> None:
    use_case, _, tender_repo, _, _ = await armar_caso()
    tender_id = uuid4()
    tender_repo.tenders[tender_id] = crear_licitacion(tender_id)

    with pytest.raises(SupplierNotFoundForUser):
        await use_case.execute(user_id=uuid4(), tender_id=tender_id)


@pytest.mark.asyncio
async def test_licitacion_inexistente_falla() -> None:
    use_case, _, _, _, supplier = await armar_caso()

    with pytest.raises(TenderNotFound):
        await use_case.execute(user_id=supplier.user_id, tender_id=uuid4())


@pytest.mark.asyncio
async def test_no_calcula_una_licitacion_cerrada() -> None:
    """A una licitación cerrada ya no se postula: el puntaje no ayuda a decidir nada."""
    use_case, _, tender_repo, matching_result_repo, supplier = await armar_caso()
    tender_id = uuid4()
    tender_repo.tenders[tender_id] = crear_licitacion(tender_id, cierra_en_horas=-2)

    with pytest.raises(TenderClosedForScoring):
        await use_case.execute(user_id=supplier.user_id, tender_id=tender_id)

    assert await matching_result_repo.get_by_supplier_id(supplier.id) == []


@pytest.mark.asyncio
async def test_no_calcula_una_licitacion_en_estado_no_activo() -> None:
    use_case, _, tender_repo, _, supplier = await armar_caso()
    tender_id = uuid4()
    tender_repo.tenders[tender_id] = crear_licitacion(
        tender_id, status_code=TENDER_STATUSES["CANCELLED"]
    )

    with pytest.raises(TenderClosedForScoring):
        await use_case.execute(user_id=supplier.user_id, tender_id=tender_id)
