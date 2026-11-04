"""Pruebas de la ficha de licitación: el puntaje es el de la empresa activa (#260)."""

from uuid import uuid4

import pytest

from app.application.use_cases.tender.get_tender_detail import GetTenderDetailUseCase
from app.domain.entities.matching_result import MatchingResult
from app.domain.entities.supplier import Supplier
from tests.unit.application.fakes import (
    InMemoryMatchingResultRepository,
    InMemorySupplierRepository,
    InMemoryTenderRepository,
)
from tests.unit.application.test_score_tender_on_demand import crear_licitacion


@pytest.mark.asyncio
async def test_muestra_el_puntaje_de_la_empresa_activa():
    suppliers = InMemorySupplierRepository()
    tenders = InMemoryTenderRepository()
    matching = InMemoryMatchingResultRepository()
    user_id = uuid4()
    propia = await suppliers.save(
        Supplier(rut="76.086.428-5", legal_name="Propia SpA", user_id=user_id)
    )
    activa = await suppliers.save(
        Supplier(rut="77.654.321-7", legal_name="Activa Ltda", user_id=uuid4())
    )
    tender_id = uuid4()
    tenders.tenders[tender_id] = crear_licitacion(tender_id)
    for supplier, score in ((propia, 0.2), (activa, 0.9)):
        await matching.save_bulk(
            [
                MatchingResult(
                    supplier_id=supplier.id,
                    tender_id=tender_id,
                    final_score=score,
                    model_version="test",
                )
            ]
        )
    use_case = GetTenderDetailUseCase(
        tender_repo=tenders, supplier_repo=suppliers, matching_result_repo=matching
    )

    detalle = await use_case.execute(
        user_id=user_id, tender_id=tender_id, supplier_id=activa.id
    )

    assert detalle.final_score == 0.9


async def _detalle_con_fila(source: str | None, cierra_en_horas: int = 48):
    """Ficha de una licitación con una fila de matching del origen indicado."""
    suppliers = InMemorySupplierRepository()
    tenders = InMemoryTenderRepository()
    matching = InMemoryMatchingResultRepository()
    user_id = uuid4()
    supplier = await suppliers.save(
        Supplier(rut="76.086.428-5", legal_name="Propia SpA", user_id=user_id)
    )
    tender_id = uuid4()
    tenders.tenders[tender_id] = crear_licitacion(
        tender_id, cierra_en_horas=cierra_en_horas
    )
    if source is not None:
        await matching.save_bulk(
            [
                MatchingResult(
                    supplier_id=supplier.id,
                    tender_id=tender_id,
                    final_score=0.8,
                    model_version="test",
                    source=source,
                )
            ]
        )
    use_case = GetTenderDetailUseCase(
        tender_repo=tenders, supplier_repo=suppliers, matching_result_repo=matching
    )
    return await use_case.execute(
        user_id=user_id, tender_id=tender_id, supplier_id=supplier.id
    )


@pytest.mark.asyncio
async def test_es_recomendada_si_la_fila_viene_del_ranking():
    detalle = await _detalle_con_fila("ranking")

    assert detalle.is_recommended is True


@pytest.mark.asyncio
async def test_un_calculo_a_pedido_no_la_vuelve_recomendada():
    detalle = await _detalle_con_fila("on_demand")

    assert detalle.is_recommended is False


@pytest.mark.asyncio
async def test_sin_puntaje_no_es_recomendada():
    detalle = await _detalle_con_fila(None)

    assert detalle.is_recommended is False


@pytest.mark.asyncio
async def test_una_cerrada_no_es_recomendada_aunque_siga_en_el_ranking_cacheado():
    # `/recommended` descarta las cerradas, pero la fila cacheada puede seguir
    # ahí hasta la próxima corrida del ranking.
    detalle = await _detalle_con_fila("ranking", cierra_en_horas=-1)

    assert detalle.is_recommended is False
