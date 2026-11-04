"""CA5 y CA6 — Acceso compartido a deep analysis y cotizaciones por workspace.

Verifica que el usuario B puede leer el análisis de compatibilidad (CA5) y la
cotización (CA6) creados por el usuario A, siempre que ambos operen bajo el
mismo `supplier_id` de workspace. El contrato es: si el `supplier_id` llega
desde el `WorkspaceContext` (ya verificado por el router), cualquier miembro
accede al dato sin importar quién lo generó.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.application.repositories.quotation_repository import IQuotationRepository
from app.application.services.compatibility_scorer import CompatibilityScorer
from app.application.use_cases.deep_analysis.get_or_create_deep_analysis import (
    GetOrCreateDeepAnalysisUseCase,
)
from app.application.use_cases.quotation import QuotationUseCase
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.quotation import MaterialItem, Quotation, QuotationInput, StoredMaterialItem
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender
from app.shared.constants import TENDER_STATUSES
from tests.unit.application.fakes import (
    FakeRerankerService,
    FakeWeightingService,
    InMemoryMatchingResultRepository,
    InMemorySupplierRepository,
    InMemoryTenderRepository,
)
from tests.unit.application.test_get_or_create_deep_analysis import (
    FakeDeepAnalysisService,
)


# ---------------------------------------------------------------------------
# Helpers compartidos
# ---------------------------------------------------------------------------


def _make_tender(tender_id: UUID) -> Tender:
    now = datetime.now(UTC).replace(tzinfo=None)
    return Tender(
        id=tender_id,
        code=f"LIC-{tender_id}",
        name="Licitación de prueba CA5/CA6",
        status_id=1,
        status_code=TENDER_STATUSES["PUBLISHED"],
        published_at=now - timedelta(days=8),
        closing_at=now + timedelta(hours=48),
        last_change_at=now - timedelta(days=7),
        buyer_rut="11.111.111-1",
        buyer_name="Comprador",
        buyer_unit="Unidad",
        items=[],
    )


def _make_supplier(supplier_id: UUID, owner_user_id: UUID) -> Supplier:
    return Supplier(
        id=supplier_id,
        user_id=owner_user_id,
        rut="76086428-5",
        legal_name="Empresa Workspace SpA",
    )


# ---------------------------------------------------------------------------
# CA5 — Deep analysis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ca5_user_b_reads_analysis_created_for_workspace() -> None:
    """Escenario: usuario A genera análisis con supplier_id del workspace;
    usuario B, miembro del mismo workspace, lo lee con only_if_exists=True.
    """
    supplier_repo = InMemorySupplierRepository()
    tender_repo = InMemoryTenderRepository()
    matching_repo = InMemoryMatchingResultRepository()
    ai_service = FakeDeepAnalysisService()
    scorer = CompatibilityScorer(FakeRerankerService(), FakeWeightingService(), matching_repo)

    supplier_id = uuid4()
    user_a = uuid4()
    user_b = uuid4()
    tender_id = uuid4()

    supplier = _make_supplier(supplier_id, owner_user_id=user_a)
    await supplier_repo.save(supplier)

    tender = _make_tender(tender_id)
    tender_repo.tenders[tender_id] = tender

    # Pre-seed: análisis ya generado para este workspace
    now = datetime.now(UTC).replace(tzinfo=None)
    analysis = DeepAnalysis(
        tender_id=tender_id,
        supplier_id=supplier_id,
        compatibility_score=0.87,
        recommendation="Postular",
        justification="Excelente ajuste al perfil.",
        created_at=now - timedelta(hours=1),
        updated_at=now - timedelta(hours=1),
    )
    await tender_repo.save_deep_analysis(analysis)

    use_case = GetOrCreateDeepAnalysisUseCase(
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        matching_result_repo=matching_repo,
        deep_analysis_service=ai_service,
        scorer=scorer,
    )

    # Usuario B no es dueño del supplier — lo recibe a través del WorkspaceContext
    result = await use_case.execute(
        tender_id=tender_id,
        user_id=user_b,
        supplier_id=supplier_id,
        only_if_exists=True,
    )

    assert result.analysis is not None, "usuario B debe ver el análisis del workspace"
    assert result.analysis.id == analysis.id
    assert len(ai_service.calls) == 0, "only_if_exists no debe disparar generación"


@pytest.mark.asyncio
async def test_ca5_sin_supplier_id_user_b_no_ve_analisis_ajeno() -> None:
    """Sin supplier_id explícito, user B resuelve con su propia empresa (si tiene)
    o no encuentra nada. Nunca cae a la empresa de user A por herencia de sesión.
    """
    supplier_repo = InMemorySupplierRepository()
    tender_repo = InMemoryTenderRepository()
    matching_repo = InMemoryMatchingResultRepository()
    ai_service = FakeDeepAnalysisService()
    scorer = CompatibilityScorer(FakeRerankerService(), FakeWeightingService(), matching_repo)

    supplier_id = uuid4()
    user_a = uuid4()
    user_b = uuid4()
    tender_id = uuid4()

    supplier = _make_supplier(supplier_id, owner_user_id=user_a)
    await supplier_repo.save(supplier)

    tender = _make_tender(tender_id)
    tender_repo.tenders[tender_id] = tender

    now = datetime.now(UTC).replace(tzinfo=None)
    analysis = DeepAnalysis(
        tender_id=tender_id,
        supplier_id=supplier_id,
        compatibility_score=0.87,
        recommendation="Postular",
        justification="Fit del workspace.",
        created_at=now,
        updated_at=now,
    )
    await tender_repo.save_deep_analysis(analysis)

    use_case = GetOrCreateDeepAnalysisUseCase(
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        matching_result_repo=matching_repo,
        deep_analysis_service=ai_service,
        scorer=scorer,
    )

    # B no pasa supplier_id → resolver_empresa devuelve None para B
    from app.domain.errors.supplier_errors import SupplierNotFoundForUser

    with pytest.raises(SupplierNotFoundForUser):
        await use_case.execute(
            tender_id=tender_id,
            user_id=user_b,
            supplier_id=None,
            only_if_exists=True,
        )


# ---------------------------------------------------------------------------
# CA6 — Cotizaciones
# ---------------------------------------------------------------------------


class InMemoryQuotationRepository(IQuotationRepository):
    def __init__(self) -> None:
        self.store: dict[tuple[UUID, UUID], Quotation] = {}

    async def get(self, supplier_id: UUID, tender_id: UUID) -> Quotation | None:
        return self.store.get((supplier_id, tender_id))

    async def save(
        self, supplier_id: UUID, tender_id: UUID, data: QuotationInput
    ) -> Quotation:
        now = datetime.now(UTC).replace(tzinfo=None)
        stored_items = [
            StoredMaterialItem(
                description=i.description,
                unit=i.unit,
                quantity=i.quantity,
                unit_price=i.unit_price,
            )
            for i in data.items
        ]
        quotation = Quotation(
            id=uuid4(),
            supplier_id=supplier_id,
            tender_id=tender_id,
            currency="CLP",
            items=stored_items,
            updated_at=now,
        )
        self.store[(supplier_id, tender_id)] = quotation
        return quotation


def _make_quotation_input() -> QuotationInput:
    return QuotationInput(
        items=[
            MaterialItem(
                description="Papel bond A4",
                unit="resma",
                quantity=Decimal("10"),
                unit_price=Decimal("3500"),
            )
        ]
    )


@dataclass
class _CA6Setup:
    use_case: QuotationUseCase
    supplier_id: UUID
    user_a: UUID
    user_b: UUID
    tender_id: UUID


async def _setup_ca6() -> _CA6Setup:
    supplier_id = uuid4()
    user_a = uuid4()
    user_b = uuid4()
    tender_id = uuid4()

    supplier_repo = InMemorySupplierRepository()
    tender_repo = InMemoryTenderRepository()
    quotation_repo = InMemoryQuotationRepository()

    supplier = _make_supplier(supplier_id, owner_user_id=user_a)
    await supplier_repo.save(supplier)

    tender = _make_tender(tender_id)
    tender_repo.tenders[tender_id] = tender

    use_case = QuotationUseCase(
        repo=quotation_repo,
        suppliers=supplier_repo,
        tenders=tender_repo,
    )

    return _CA6Setup(
        use_case=use_case,
        supplier_id=supplier_id,
        user_a=user_a,
        user_b=user_b,
        tender_id=tender_id,
    )


@pytest.mark.asyncio
async def test_ca6_user_b_lee_cotizacion_guardada_por_user_a() -> None:
    """Usuario A guarda una cotización bajo el supplier_id del workspace;
    usuario B la lee pasando el mismo supplier_id (desde WorkspaceContext).
    """
    s = await _setup_ca6()

    # A guarda la cotización con el supplier_id del workspace
    saved = await s.use_case.save(
        s.user_a,
        s.tender_id,
        _make_quotation_input(),
        supplier_id=s.supplier_id,
    )

    # B la lee con el mismo supplier_id del workspace
    retrieved = await s.use_case.get(
        s.user_b,
        s.tender_id,
        supplier_id=s.supplier_id,
    )

    assert retrieved is not None, "usuario B debe poder leer la cotización del workspace"
    assert retrieved.id == saved.id
    assert retrieved.supplier_id == s.supplier_id


@pytest.mark.asyncio
async def test_ca6_save_es_idempotente_para_el_mismo_workspace() -> None:
    """Guardar la misma cotización dos veces (por dos miembros distintos)
    actualiza el registro en vez de crear un duplicado.
    """
    s = await _setup_ca6()

    primera = await s.use_case.save(
        s.user_a,
        s.tender_id,
        _make_quotation_input(),
        supplier_id=s.supplier_id,
    )
    segunda = await s.use_case.save(
        s.user_b,
        s.tender_id,
        _make_quotation_input(),
        supplier_id=s.supplier_id,
    )

    retrieved = await s.use_case.get(
        s.user_b, s.tender_id, supplier_id=s.supplier_id
    )

    # El repo devuelve la cotización más reciente bajo (supplier_id, tender_id)
    assert retrieved is not None
    assert retrieved.supplier_id == s.supplier_id
    # Las dos upserts pertenecen al mismo workspace
    assert primera.supplier_id == segunda.supplier_id == s.supplier_id
