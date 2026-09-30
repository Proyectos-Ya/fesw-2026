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
