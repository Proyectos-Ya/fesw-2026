"""Pruebas unitarias para BuildPostulationPackageUseCase (HU-032, CA1-CA8)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.application.use_cases.proposals.build_postulation_package import (
    BuildPostulationPackageUseCase,
    normalizar_texto,
)
from app.config import Settings
from app.domain.entities.proposal import (
    DraftContent,
    DraftParagraph,
    DraftSection,
    ProposalDraft,
    TechnicalDocument,
    TechnicalSection,
)
from app.domain.entities.quotation import Quotation, StoredMaterialItem
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender, TenderItem
from app.domain.errors.proposal_errors import (
    PostulationFeatureDisabled,
    ProposalDraftNotFound,
    ProposalDraftNotReady,
)
from app.domain.errors.tender_errors import TenderClosedForProposal
from app.shared.constants import TENDER_STATUSES
from tests.unit.application.fakes import (
    InMemoryProposalDraftRepository,
    InMemorySupplierRepository,
    InMemoryTenderRepository,
)


class InMemoryQuotationRepository:
    def __init__(self, cotizaciones: list[Quotation] | None = None) -> None:
        self.items: dict[tuple[UUID, UUID], Quotation] = {
            (c.supplier_id, c.tender_id): c for c in (cotizaciones or [])
        }

    async def get(self, supplier_id: UUID, tender_id: UUID) -> Quotation | None:
        return self.items.get((supplier_id, tender_id))

    async def save(self, supplier_id: UUID, tender_id: UUID, data: object) -> Quotation:
        raise NotImplementedError


def _crear_entorno(postulation_enabled: bool = True):
    settings = MagicMock(spec=Settings)
    settings.extension_enabled = True
    settings.extension_postulation_enabled = postulation_enabled

    suppliers = InMemorySupplierRepository()
    tenders = InMemoryTenderRepository()
    drafts = InMemoryProposalDraftRepository()
    quotations = InMemoryQuotationRepository()

    use_case = BuildPostulationPackageUseCase(
        supplier_repo=suppliers,
        tender_repo=tenders,
        draft_repo=drafts,
        quotation_repo=quotations,
        settings=settings,
    )
    return use_case, suppliers, tenders, drafts, quotations, settings


def _crear_licitacion(
    tender_id: UUID,
    code: str = "1234-56-COT26",
    name: str = "Compra de Café",
    items: list[TenderItem] | None = None,
    cerrada: bool = False,
) -> Tender:
    ahora = datetime.now(UTC).replace(tzinfo=None)
    closing = ahora - timedelta(days=1) if cerrada else ahora + timedelta(days=2)
    status_code = TENDER_STATUSES["CLOSED"] if cerrada else TENDER_STATUSES["PUBLISHED"]
    return Tender(
        id=tender_id,
        code=code,
        name=name,
        description="Descripción",
        status_id=1,
        status_code=status_code,
        published_at=ahora - timedelta(days=1),
        closing_at=closing,
        last_change_at=ahora,
        buyer_rut="60.504.000-9",
        buyer_unit="Depto Abastecimiento",
        items=items or [],
    )


def _crear_draft_content() -> DraftContent:
    return DraftContent(
        offer_name=DraftSection(
            paragraphs=[DraftParagraph(text="Servicio de Café y Banquetería")]
        ),
        offer_description=DraftSection(
            paragraphs=[
                DraftParagraph(
                    text="Provisión de insumos de cafetería. (Por favor, inserte aquí el valor plazo)",
                    placeholders=["plazo"],
                )
            ]
        ),
        required_documents=DraftSection(
            paragraphs=[DraftParagraph(text="Certificado de antecedentes laborales")]
        ),
        technical_document=TechnicalDocument(
            sections=[
                TechnicalSection(
                    key="metodologia",
                    title="Metodología",
                    paragraphs=[DraftParagraph(text="Plan de entregas periódicas")],
                )
            ]
        ),
    )


def test_normalizar_texto():
    assert normalizar_texto("  Café  en GRANO   1kg  ") == "cafe en grano 1kg"
    assert normalizar_texto("Términos & CONDICIONES") == "terminos & condiciones"
    assert normalizar_texto("") == ""


@pytest.mark.asyncio
async def test_matching_exacto_por_descripcion_normalizada():
    use_case, suppliers, tenders, drafts, quotations, _ = _crear_entorno()

    user_id = uuid4()
    supplier = Supplier(id=uuid4(), user_id=user_id, rut="76.086.428-5", legal_name="Café Gourmet SpA")
    suppliers.suppliers[str(supplier.id)] = supplier

    tender_id = uuid4()
    tender = _crear_licitacion(
        tender_id=tender_id,
        items=[
            TenderItem(
                id=uuid4(),
                tender_id=tender_id,
                product_code="50201706",
                name="Café Arábica",
                description="Café en Grano Tostado 1Kg",
                quantity=10,
                unit_of_measure="Kilos",
            )
        ],
    )
    tenders.tenders[tender.id] = tender

    draft = ProposalDraft(
        id=uuid4(),
        supplier_id=supplier.id,
        tender_id=tender_id,
        status="READY",
        content=_crear_draft_content(),
    )
    await drafts.save(draft)

    quotation = Quotation(
        id=uuid4(),
        supplier_id=supplier.id,
        tender_id=tender_id,
        currency="CLP",
        updated_at=datetime.now(UTC),
        items=[
            StoredMaterialItem(
                description="café en grano tostado 1kg",
                unit="Kilos",
                quantity=Decimal("10"),
                unit_price=Decimal("12500"),
            )
        ],
        shipping_clp=Decimal("15000"),
    )
    quotations.items[(supplier.id, tender_id)] = quotation

    package = await use_case.execute(user_id=user_id, supplier_id=supplier.id, tender_id=tender_id)

    assert package.shipping_clp == 15000
    assert package.tender.code == "1234-56-COT26"
    assert package.company.rut == "76.086.428-5"
    assert package.offer_name == "Servicio de Café y Banquetería"
    assert package.offer_description_placeholders == ["plazo"]
    assert package.technical_document_available is True
    assert len(package.items) == 1
    item = package.items[0]
    assert item.position == 1
    assert item.unit_price == 12500
    assert item.price_source == "cotizacion"
    assert item.quotation_quantity == 10.0


@pytest.mark.asyncio
async def test_primer_material_sin_usar_gana_y_advierte_sobrante():
    use_case, suppliers, tenders, drafts, quotations, _ = _crear_entorno()

    user_id = uuid4()
    supplier = Supplier(id=uuid4(), user_id=user_id, rut="76.086.428-5", legal_name="Test SpA")
    suppliers.suppliers[str(supplier.id)] = supplier

    tender_id = uuid4()
    tender = _crear_licitacion(
        tender_id=tender_id,
        items=[
            TenderItem(id=uuid4(), tender_id=tender_id, product_code="1", name="Item A", description="Mismo Item", quantity=5, unit_of_measure="U"),
            TenderItem(id=uuid4(), tender_id=tender_id, product_code="2", name="Item B", description="Mismo Item", quantity=5, unit_of_measure="U"),
        ],
    )
    tenders.tenders[tender.id] = tender

    draft = ProposalDraft(
        id=uuid4(),
        supplier_id=supplier.id,
        tender_id=tender_id,
        status="READY",
        content=_crear_draft_content(),
    )
    await drafts.save(draft)

    quotation = Quotation(
        id=uuid4(),
        supplier_id=supplier.id,
        tender_id=tender_id,
        currency="CLP",
        updated_at=datetime.now(UTC),
        items=[
            StoredMaterialItem(description="Mismo Item", unit="U", quantity=Decimal("5"), unit_price=Decimal("1000")),
            StoredMaterialItem(description="Mismo Item", unit="U", quantity=Decimal("5"), unit_price=Decimal("2000")),
            StoredMaterialItem(description="Item Sobrante Sin Match", unit="U", quantity=Decimal("1"), unit_price=Decimal("500")),
        ],
    )
    quotations.items[(supplier.id, tender_id)] = quotation

    package = await use_case.execute(user_id=user_id, supplier_id=supplier.id, tender_id=tender_id)

    assert package.items[0].unit_price == 1000
    assert package.items[1].unit_price == 2000
    # Sobrante genera advertencia
    assert any("Item Sobrante Sin Match" in w for w in package.warnings)


@pytest.mark.asyncio
async def test_item_sin_match_da_sin_precio():
    use_case, suppliers, tenders, drafts, quotations, _ = _crear_entorno()

    user_id = uuid4()
    supplier = Supplier(id=uuid4(), user_id=user_id, rut="76.086.428-5", legal_name="Test SpA")
    suppliers.suppliers[str(supplier.id)] = supplier

    tender_id = uuid4()
    tender = _crear_licitacion(
        tender_id=tender_id,
        items=[
            TenderItem(id=uuid4(), tender_id=tender_id, product_code="1", name="Servicio Consultoría", description="Asesoría legal", quantity=1, unit_of_measure="U")
        ],
    )
    tenders.tenders[tender.id] = tender

    draft = ProposalDraft(
        id=uuid4(),
        supplier_id=supplier.id,
        tender_id=tender_id,
        status="READY",
        content=_crear_draft_content(),
    )
    await drafts.save(draft)

    quotation = Quotation(
        id=uuid4(),
        supplier_id=supplier.id,
        tender_id=tender_id,
        currency="CLP",
        updated_at=datetime.now(UTC),
        items=[
            StoredMaterialItem(description="Servicio Limpieza", unit="U", quantity=Decimal("1"), unit_price=Decimal("5000"))
        ],
    )
    quotations.items[(supplier.id, tender_id)] = quotation

    package = await use_case.execute(user_id=user_id, supplier_id=supplier.id, tender_id=tender_id)

    assert package.items[0].unit_price is None
    assert package.items[0].price_source == "sin_precio"


@pytest.mark.asyncio
async def test_cotizacion_otra_moneda_da_todo_sin_precio():
    use_case, suppliers, tenders, drafts, quotations, _ = _crear_entorno()

    user_id = uuid4()
    supplier = Supplier(id=uuid4(), user_id=user_id, rut="76.086.428-5", legal_name="Test SpA")
    suppliers.suppliers[str(supplier.id)] = supplier

    tender_id = uuid4()
    tender = _crear_licitacion(
        tender_id=tender_id,
        items=[
            TenderItem(id=uuid4(), tender_id=tender_id, product_code="1", name="Item A", description="Item A", quantity=1, unit_of_measure="U")
        ],
    )
    tenders.tenders[tender.id] = tender

    draft = ProposalDraft(
        id=uuid4(),
        supplier_id=supplier.id,
        tender_id=tender_id,
        status="READY",
        content=_crear_draft_content(),
    )
    await drafts.save(draft)

    quotation = Quotation(
        id=uuid4(),
        supplier_id=supplier.id,
        tender_id=tender_id,
        currency="USD",
        updated_at=datetime.now(UTC),
        items=[
            StoredMaterialItem(description="Item A", unit="U", quantity=Decimal("1"), unit_price=Decimal("100"))
        ],
    )
    quotations.items[(supplier.id, tender_id)] = quotation

    package = await use_case.execute(user_id=user_id, supplier_id=supplier.id, tender_id=tender_id)

    assert package.items[0].unit_price is None
    assert package.items[0].price_source == "sin_precio"
    assert any("moneda distinta a CLP" in w for w in package.warnings)


@pytest.mark.asyncio
async def test_cantidad_distinta_genera_advertencia():
    use_case, suppliers, tenders, drafts, quotations, _ = _crear_entorno()

    user_id = uuid4()
    supplier = Supplier(id=uuid4(), user_id=user_id, rut="76.086.428-5", legal_name="Test SpA")
    suppliers.suppliers[str(supplier.id)] = supplier

    tender_id = uuid4()
    tender = _crear_licitacion(
        tender_id=tender_id,
        items=[
            TenderItem(id=uuid4(), tender_id=tender_id, product_code="1", name="Item A", description="Item A", quantity=5, unit_of_measure="U")
        ],
    )
    tenders.tenders[tender.id] = tender

    draft = ProposalDraft(
        id=uuid4(),
        supplier_id=supplier.id,
        tender_id=tender_id,
        status="READY",
        content=_crear_draft_content(),
    )
    await drafts.save(draft)

    quotation = Quotation(
        id=uuid4(),
        supplier_id=supplier.id,
        tender_id=tender_id,
        currency="CLP",
        updated_at=datetime.now(UTC),
        items=[
            StoredMaterialItem(description="Item A", unit="U", quantity=Decimal("10"), unit_price=Decimal("1000"))
        ],
    )
    quotations.items[(supplier.id, tender_id)] = quotation

    package = await use_case.execute(user_id=user_id, supplier_id=supplier.id, tender_id=tender_id)

    assert package.items[0].unit_price == 1000
    assert any("difiere" in w for w in package.warnings)


@pytest.mark.asyncio
async def test_sin_cotizacion_todo_sin_precio():
    use_case, suppliers, tenders, drafts, _, _ = _crear_entorno()

    user_id = uuid4()
    supplier = Supplier(id=uuid4(), user_id=user_id, rut="76.086.428-5", legal_name="Test SpA")
    suppliers.suppliers[str(supplier.id)] = supplier

    tender_id = uuid4()
    tender = _crear_licitacion(
        tender_id=tender_id,
        items=[
            TenderItem(id=uuid4(), tender_id=tender_id, product_code="1", name="Item A", description="Item A", quantity=1, unit_of_measure="U")
        ],
    )
    tenders.tenders[tender.id] = tender

    draft = ProposalDraft(
        id=uuid4(),
        supplier_id=supplier.id,
        tender_id=tender_id,
        status="READY",
        content=_crear_draft_content(),
    )
    await drafts.save(draft)

    package = await use_case.execute(user_id=user_id, supplier_id=supplier.id, tender_id=tender_id)

    assert package.items[0].unit_price is None
    assert package.items[0].price_source == "sin_precio"


@pytest.mark.asyncio
async def test_error_409_licitacion_cerrada():
    use_case, suppliers, tenders, drafts, _, _ = _crear_entorno()

    user_id = uuid4()
    supplier = Supplier(id=uuid4(), user_id=user_id, rut="76.086.428-5", legal_name="Test SpA")
    suppliers.suppliers[str(supplier.id)] = supplier

    tender_id = uuid4()
    tender = _crear_licitacion(
        tender_id=tender_id,
        name="Cerrada",
        cerrada=True,
    )
    tenders.tenders[tender.id] = tender

    with pytest.raises(TenderClosedForProposal):
        await use_case.execute(user_id=user_id, supplier_id=supplier.id, tender_id=tender_id)


@pytest.mark.asyncio
async def test_error_409_sin_content():
    use_case, suppliers, tenders, drafts, _, _ = _crear_entorno()

    user_id = uuid4()
    supplier = Supplier(id=uuid4(), user_id=user_id, rut="76.086.428-5", legal_name="Test SpA")
    suppliers.suppliers[str(supplier.id)] = supplier

    tender_id = uuid4()
    tender = _crear_licitacion(
        tender_id=tender_id,
        name="Abierta",
    )
    tenders.tenders[tender.id] = tender

    draft = ProposalDraft(
        id=uuid4(),
        supplier_id=supplier.id,
        tender_id=tender_id,
        status="FEASIBILITY",
        content=None,
    )
    await drafts.save(draft)

    with pytest.raises(ProposalDraftNotReady):
        await use_case.execute(user_id=user_id, supplier_id=supplier.id, tender_id=tender_id)


@pytest.mark.asyncio
async def test_error_404_sin_borrador():
    use_case, suppliers, tenders, _, _, _ = _crear_entorno()

    user_id = uuid4()
    supplier = Supplier(id=uuid4(), user_id=user_id, rut="76.086.428-5", legal_name="Test SpA")
    suppliers.suppliers[str(supplier.id)] = supplier

    tender_id = uuid4()
    tender = _crear_licitacion(
        tender_id=tender_id,
        name="Abierta",
    )
    tenders.tenders[tender.id] = tender

    with pytest.raises(ProposalDraftNotFound):
        await use_case.execute(user_id=user_id, supplier_id=supplier.id, tender_id=tender_id)


@pytest.mark.asyncio
async def test_error_503_flag_apagado():
    use_case, suppliers, _, _, _, settings = _crear_entorno(postulation_enabled=False)

    user_id = uuid4()
    supplier = Supplier(id=uuid4(), user_id=user_id, rut="76.086.428-5", legal_name="Test SpA")
    suppliers.suppliers[str(supplier.id)] = supplier

    with pytest.raises(PostulationFeatureDisabled):
        await use_case.execute(user_id=user_id, supplier_id=supplier.id, tender_id=uuid4())
