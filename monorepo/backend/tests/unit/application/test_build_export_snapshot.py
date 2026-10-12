from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.use_cases.exports.build_export_snapshot import (
    BuildExportSnapshotUseCase,
)
from app.application.use_cases.exports.export_snapshot import ExportSection
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.matching_result import MatchingResult
from app.domain.entities.quotation import MaterialItem, QuotationInput
from app.domain.entities.supplier_member import MemberRole, WorkspaceContext
from app.domain.entities.tender import Tender
from app.domain.errors.export_errors import ExportForbidden
from app.domain.errors.tender_errors import TenderNotFound
from tests.unit.application.export_fakes import InMemoryQuotationRepository
from tests.unit.application.fakes import (
    InMemoryMatchingResultRepository,
    InMemoryTenderRepository,
)

AHORA = datetime(2026, 9, 28, 12, 0, 0)
EMPRESA = uuid4()


def _contexto(permisos: list[str] | None = None) -> WorkspaceContext:
    return WorkspaceContext(
        user_id=uuid4(),
        active_supplier_id=EMPRESA,
        active_supplier_name="Constructora Andes",
        role=MemberRole.MEMBER,
        permissions=["view_matches"] if permisos is None else permisos,
    )


class Escenario:
    def __init__(self) -> None:
        self.tenders = InMemoryTenderRepository()
        self.matching = InMemoryMatchingResultRepository()
        self.quotations = InMemoryQuotationRepository()
        self.tender = Tender(
            code="1057539-228-COT26",
            name="Mantención de áreas verdes",
            status_id=1,
            status_code="publicada",
            published_at=AHORA - timedelta(days=2),
            closing_at=AHORA + timedelta(days=10),
            last_change_at=AHORA,
            buyer_rut="61.980.170-9",
            buyer_name="Municipalidad de Providencia",
            buyer_unit="Operaciones",
            available_amount_clp=5_000_000,
        )
        self.tenders.tenders[self.tender.id] = self.tender
        self.use_case = BuildExportSnapshotUseCase(
            tenders=self.tenders,
            matching_results=self.matching,
            quotations=self.quotations,
            now=lambda: AHORA,
        )


@pytest.fixture
def esc() -> Escenario:
    return Escenario()


async def test_reune_licitacion_puntaje_analisis_y_cotizacion_de_la_empresa_activa(esc):
    await esc.matching.save_on_demand(
        MatchingResult(
            supplier_id=EMPRESA,
            tender_id=esc.tender.id,
            final_score=0.84,
            model_version="test",
            source="on_demand",
        )
    )
    await esc.tenders.save_deep_analysis(
        DeepAnalysis(
            tender_id=esc.tender.id,
            supplier_id=EMPRESA,
            compatibility_score=84,
            recommendation="Postular",
            justification="El rubro coincide.",
        )
    )
    await esc.quotations.save(
        EMPRESA,
        esc.tender.id,
        QuotationInput(
            items=[
                MaterialItem(
                    description="Pasto", unit="m2", quantity=Decimal("10"), unit_price=Decimal("1500")
                )
            ]
        ),
    )

    snapshot = await esc.use_case.execute(_contexto(), esc.tender.id)

    assert snapshot.tender.id == esc.tender.id
    assert snapshot.supplier_name == "Constructora Andes"
    assert snapshot.score_pct == 84
    assert snapshot.analysis is not None
    assert snapshot.quotation is not None
    assert snapshot.quotation.total == Decimal("15000.00")
    assert snapshot.generated_at == AHORA


async def test_las_fechas_clave_son_la_publicacion_y_el_cierre(esc):
    # Hasta que la HU-16 llegue a develop, los hitos son las fechas oficiales.
    snapshot = await esc.use_case.execute(_contexto(), esc.tender.id)

    assert [(f.label, f.at) for f in snapshot.key_dates] == [
        ("Publicación", esc.tender.published_at),
        ("Cierre de postulación", esc.tender.closing_at),
    ]


async def test_sin_puntaje_analisis_ni_cotizacion_igual_exporta(esc):
    snapshot = await esc.use_case.execute(_contexto(), esc.tender.id)

    assert snapshot.score_pct is None
    assert snapshot.analysis is None
    assert snapshot.quotation is None


async def test_no_mezcla_datos_de_otra_empresa(esc):
    otra = uuid4()
    await esc.tenders.save_deep_analysis(
        DeepAnalysis(
            tender_id=esc.tender.id,
            supplier_id=otra,
            compatibility_score=10,
            recommendation="No recomendado",
            justification="De otra empresa.",
        )
    )
    await esc.quotations.save(
        otra,
        esc.tender.id,
        QuotationInput(
            items=[MaterialItem(description="X", unit="u", quantity=Decimal(1), unit_price=Decimal(1))]
        ),
    )

    snapshot = await esc.use_case.execute(_contexto(), esc.tender.id)

    assert snapshot.analysis is None
    assert snapshot.quotation is None


async def test_la_licitacion_tiene_que_existir(esc):
    with pytest.raises(TenderNotFound):
        await esc.use_case.execute(_contexto(), uuid4())


async def test_sin_permiso_de_ver_licitaciones_no_exporta(esc):
    with pytest.raises(ExportForbidden):
        await esc.use_case.execute(_contexto(permisos=[]), esc.tender.id)


def test_las_secciones_del_excel():
    # Criterio 5: lo que el usuario puede marcar o desmarcar.
    assert [s.value for s in ExportSection] == [
        "datos_generales",
        "montos",
        "items",
        "hitos",
        "analisis_ia",
    ]
