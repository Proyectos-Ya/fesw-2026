"""El repositorio de matching separa el top-N del ranking de los cálculos a pedido.

La separación tiene que ser real en SQL: el pipeline borra y reescribe sus filas
en cada recálculo, y lo que el usuario pidió a mano debe quedar en pie.

`db_session` y el esquema limpio los aporta tests/integration/conftest.py, que
apunta a la base de test y no a la de desarrollo.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.entities.matching_result import MatchingResult
from app.infrastructure.repositories.matching_result_repository import (
    MatchingResultRepository,
)
from app.infrastructure.repositories.supplier_model import SupplierModel
from app.infrastructure.repositories.tender_model import (
    BuyerInstitutionModel,
    RegionModel,
    TenderModel,
    TenderStatusModel,
)
from app.shared.regions import CHILE_REGIONS


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def sembrar(
    session: AsyncSession, supplier_id: UUID, tender_ids: list[UUID]
) -> None:
    """Inserta proveedor y licitaciones para poder referenciar las claves foráneas."""
    session.add(RegionModel(id=13, name=CHILE_REGIONS[13]))
    session.add(TenderStatusModel(id=1, code="publicada", name="Publicada"))
    session.add(
        BuyerInstitutionModel(
            rut="12.345.678-9",
            name="Municipalidad de Santiago",
            region_id=13,
            created_at=utc_now_naive(),
            updated_at=utc_now_naive(),
        )
    )
    session.add(
        SupplierModel(
            id=supplier_id,
            rut="76.086.428-5",
            legal_name="Empresa Ejemplo SpA",
            created_at=utc_now_naive(),
            updated_at=utc_now_naive(),
        )
    )
    for indice, tender_id in enumerate(tender_ids):
        session.add(
            TenderModel(
                id=tender_id,
                code=f"1057539-{indice}-COT26",
                name="Materiales Eléctricos",
                description="Compra de cables y enchufes",
                status_id=1,
                published_at=utc_now_naive(),
                closing_at=utc_now_naive(),
                last_change_at=utc_now_naive(),
                buyer_rut="12.345.678-9",
                buyer_unit="Operaciones",
                available_amount_clp=500000.0,
                created_at=utc_now_naive(),
                updated_at=utc_now_naive(),
            )
        )
    await session.commit()


def fila_ranking(supplier_id: UUID, tender_id: UUID) -> MatchingResult:
    return MatchingResult(
        supplier_id=supplier_id,
        tender_id=tender_id,
        similarity_score=0.80,
        reranker_score=0.75,
        final_score=0.85,
        model_version="bge-m3-v1",
        source="ranking",
        calculated_at=utc_now_naive(),
    )


def fila_a_pedido(supplier_id: UUID, tender_id: UUID) -> MatchingResult:
    return MatchingResult(
        supplier_id=supplier_id,
        tender_id=tender_id,
        similarity_score=None,
        reranker_score=0.40,
        final_score=0.42,
        model_version="bge-m3-v1",
        source="on_demand",
        calculated_at=utc_now_naive(),
    )


@pytest.mark.asyncio
async def test_el_calculo_a_pedido_se_guarda_sin_similitud(db_session: AsyncSession):
    """No pasa por Qdrant: la columna acepta NULL en vez de inventar un 0.0."""
    supplier_id, tender_id = uuid4(), uuid4()
    await sembrar(db_session, supplier_id, [tender_id])
    repo = MatchingResultRepository(db_session)

    await repo.save_on_demand(fila_a_pedido(supplier_id, tender_id))

    guardado = await repo.get_by_proveedor_and_licitacion(supplier_id, tender_id)
    assert guardado is not None
    assert guardado.similarity_score is None
    assert guardado.source == "on_demand"


@pytest.mark.asyncio
async def test_recalcular_a_pedido_reemplaza_la_fila(db_session: AsyncSession):
    """Hay una restricción única por par: recalcular sustituye, no acumula."""
    supplier_id, tender_id = uuid4(), uuid4()
    await sembrar(db_session, supplier_id, [tender_id])
    repo = MatchingResultRepository(db_session)

    await repo.save_on_demand(fila_a_pedido(supplier_id, tender_id))
    segunda = fila_a_pedido(supplier_id, tender_id)
    segunda.final_score = 0.66
    await repo.save_on_demand(segunda)

    filas = await repo.get_by_supplier_id(supplier_id)
    assert len(filas) == 1
    assert filas[0].final_score == pytest.approx(0.66)


@pytest.mark.asyncio
async def test_las_recomendaciones_excluyen_los_calculos_a_pedido(
    db_session: AsyncSession,
):
    supplier_id, recomendada, a_pedido = uuid4(), uuid4(), uuid4()
    await sembrar(db_session, supplier_id, [recomendada, a_pedido])
    repo = MatchingResultRepository(db_session)

    await repo.save_bulk([fila_ranking(supplier_id, recomendada)])
    await repo.save_on_demand(fila_a_pedido(supplier_id, a_pedido))

    ranking = await repo.get_ranking_by_supplier_id(supplier_id)
    todas = await repo.get_by_supplier_id(supplier_id)

    assert [r.tender_id for r in ranking] == [recomendada]
    assert len(todas) == 2


@pytest.mark.asyncio
async def test_borrar_el_ranking_conserva_lo_pedido_por_el_usuario(
    db_session: AsyncSession,
):
    """Es la razón de ser de la columna: el recálculo no puede llevarse esto."""
    supplier_id, recomendada, a_pedido = uuid4(), uuid4(), uuid4()
    await sembrar(db_session, supplier_id, [recomendada, a_pedido])
    repo = MatchingResultRepository(db_session)

    await repo.save_bulk([fila_ranking(supplier_id, recomendada)])
    await repo.save_on_demand(fila_a_pedido(supplier_id, a_pedido))

    await repo.delete_ranking_by_supplier_id(supplier_id)

    quedan = await repo.get_by_supplier_id(supplier_id)
    assert [r.tender_id for r in quedan] == [a_pedido]


@pytest.mark.asyncio
async def test_borrar_por_licitacion_saca_la_fila_sea_cual_sea_su_origen(
    db_session: AsyncSession,
):
    """Lo usa el ranking cuando una licitación calculada a mano entra al top."""
    supplier_id, tender_id = uuid4(), uuid4()
    await sembrar(db_session, supplier_id, [tender_id])
    repo = MatchingResultRepository(db_session)

    await repo.save_on_demand(fila_a_pedido(supplier_id, tender_id))
    await repo.delete_by_supplier_and_tender_ids(supplier_id, [tender_id])
    await repo.save_bulk([fila_ranking(supplier_id, tender_id)])

    filas = await repo.get_by_supplier_id(supplier_id)
    assert len(filas) == 1
    assert filas[0].source == "ranking"
