from uuid import uuid4

import pytest

from app.application.use_cases.feedback.report_match import ReportMatchUseCase
from app.domain.entities.feedback import MatchReportKind
from app.domain.entities.supplier import Supplier
from app.domain.errors.supplier_errors import SupplierNotFoundForUser
from app.domain.errors.tender_errors import TenderNotFound
from tests.unit.application.fakes import InMemorySupplierRepository
from tests.unit.application.feedback_fakes import InMemoryMatchReportRepository
from tests.unit.application.test_rank_tenders_use_case import (
    InMemoryTenderRepository,
    create_dummy_tender,
)


async def _armar():
    user_id = uuid4()
    supplier_repo = InMemorySupplierRepository()
    supplier = Supplier(rut="76086428-5", legal_name="Empresa SpA", user_id=user_id)
    await supplier_repo.save(supplier)
    tender_repo = InMemoryTenderRepository()
    tender_id = uuid4()
    tender_repo.tenders[tender_id] = create_dummy_tender(tender_id)
    reports = InMemoryMatchReportRepository()
    use_case = ReportMatchUseCase(
        match_report_repo=reports, tender_repo=tender_repo, supplier_repo=supplier_repo
    )
    return use_case, reports, user_id, supplier, tender_id


@pytest.mark.asyncio
async def test_guarda_el_reporte_a_nombre_de_la_empresa_activa():
    use_case, reports, user_id, supplier, tender_id = await _armar()

    report = await use_case.execute(
        user_id=user_id,
        supplier_id=None,
        tender_id=tender_id,
        kind=MatchReportKind.MATCH,
        reason="  No vendemos eso  ",
    )

    assert report.supplier_id == supplier.id
    assert report.user_id == user_id
    assert report.reason == "No vendemos eso"
    assert await reports.list_reported_tender_ids(
        supplier.id, MatchReportKind.MATCH
    ) == {tender_id}


@pytest.mark.asyncio
async def test_reportar_dos_veces_reemplaza_el_motivo():
    use_case, reports, user_id, supplier, tender_id = await _armar()
    for reason in ("Primero", "Segundo"):
        report = await use_case.execute(
            user_id=user_id,
            supplier_id=supplier.id,
            tender_id=tender_id,
            kind=MatchReportKind.ANALYSIS,
            reason=reason,
        )
    assert len(reports.reports) == 1
    assert report.reason == "Segundo"


@pytest.mark.asyncio
async def test_licitacion_inexistente_no_guarda_nada():
    use_case, reports, user_id, _, _ = await _armar()
    with pytest.raises(TenderNotFound):
        await use_case.execute(
            user_id=user_id,
            supplier_id=None,
            tender_id=uuid4(),
            kind=MatchReportKind.MATCH,
            reason="x",
        )
    assert reports.reports == {}


@pytest.mark.asyncio
async def test_usuario_sin_empresa_no_guarda_nada():
    use_case, reports, _, _, tender_id = await _armar()
    with pytest.raises(SupplierNotFoundForUser):
        await use_case.execute(
            user_id=uuid4(),
            supplier_id=None,
            tender_id=tender_id,
            kind=MatchReportKind.MATCH,
            reason="x",
        )
    assert reports.reports == {}
