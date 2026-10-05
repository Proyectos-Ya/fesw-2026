from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.document_analysis_quotation_service import (
    DocumentAnalysisAndQuotationResult,
    IDocumentAnalysisAndQuotationService,
)
from app.application.use_cases.upload_tender_chat_document_use_case import (
    UploadTenderChatDocumentResult,
    UploadTenderChatDocumentUseCase,
)
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.matching_result import MatchingResult
from app.domain.entities.quotation import MaterialItem, Quotation, QuotationInput
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender, TenderItem
from app.domain.entities.tender_chat import TenderChatDocument
from app.domain.errors.document_analysis_quotation_errors import (
    DocumentAnalysisAndQuotationServiceError,
)
from app.shared.datetime_utils import utc_now_naive
from tests.unit.application.fakes import (
    InMemoryMatchingResultRepository,
    InMemorySupplierRepository,
    InMemoryTenderChatRepository,
    InMemoryTenderRepository,
)


class FakeQuotationRepository:
    def __init__(self):
        self.quotations = {}

    async def get(self, supplier_id, tender_id):
        return self.quotations.get((supplier_id, tender_id))

    async def save(self, supplier_id, tender_id, data: QuotationInput):
        q = Quotation(
            **data.model_dump(exclude={"total": True, "items": {"__all__": {"subtotal"}}}),
            id=uuid4(),
            supplier_id=supplier_id,
            tender_id=tender_id,
            updated_at=utc_now_naive(),
        )
        self.quotations[(supplier_id, tender_id)] = q
        return q


class FakeUnifiedService(IDocumentAnalysisAndQuotationService):
    def __init__(self, result=None, raise_error=None):
        self.result = result
        self.raise_error = raise_error
        self.call_count = 0
        self.last_kwargs = {}

    async def analyze_and_quote(
        self, document_bytes, file_name, file_type, tender, supplier, matching_score=None
    ):
        self.call_count += 1
        self.last_kwargs = {
            "document_bytes": document_bytes,
            "file_name": file_name,
            "file_type": file_type,
            "tender": tender,
            "supplier": supplier,
            "matching_score": matching_score,
        }
        if self.raise_error:
            raise self.raise_error
        return self.result


def create_tender(tender_id) -> Tender:
    now = datetime.now(UTC).replace(tzinfo=None)
    return Tender(
        id=tender_id,
        code="LIC-001",
        name="Licitación Insumos",
        description="Compra de cables",
        status_id=1,
        status_code="publicada",
        published_at=now,
        closing_at=now,
        last_change_at=now,
        buyer_rut="11.111.111-1",
        buyer_name="Servicio Salud",
        buyer_unit="Compras",
        items=[
            TenderItem(
                id=uuid4(),
                tender_id=tender_id,
                name="Cable 100m",
                product_code="CAB-100",
                quantity=5,
                unit_of_measure="rollo",
            )
        ],
    )


def create_supplier(user_id) -> Supplier:
    return Supplier(
        id=uuid4(),
        user_id=user_id,
        rut="22.222.222-2",
        legal_name="Electro S.A.",
        trade_name="Electro",
        description="Fábrica de conductores",
    )


@pytest.fixture
def chat_repo():
    return InMemoryTenderChatRepository()


@pytest.fixture
def supplier_repo():
    return InMemorySupplierRepository()


@pytest.fixture
def tender_repo():
    return InMemoryTenderRepository()


@pytest.fixture
def quotation_repo():
    return FakeQuotationRepository()


@pytest.fixture
def matching_repo():
    return InMemoryMatchingResultRepository()


@pytest.mark.asyncio
async def test_upload_document_triggers_unified_analysis_and_persists_both(
    chat_repo, supplier_repo, tender_repo, quotation_repo, matching_repo
):
    user_id = uuid4()
    tender_id = uuid4()
    supplier = create_supplier(user_id)
    tender = create_tender(tender_id)

    await supplier_repo.save(supplier)
    tender_repo.tenders[tender_id] = tender

    matching_res = MatchingResult(
        id=uuid4(),
        supplier_id=supplier.id,
        tender_id=tender_id,
        final_score=0.85,
        model_version="v1.0",
        calculated_at=utc_now_naive(),
    )
    await matching_repo.save_on_demand(matching_res)

    expected_analysis = DeepAnalysis(
        id=uuid4(),
        tender_id=tender_id,
        supplier_id=supplier.id,
        compatibility_score=85.0,
        recommendation="Postular",
        justification="Excelente compatibilidad en cables de cobre.",
    )
    expected_quotation = QuotationInput(
        currency="CLP",
        items=[
            MaterialItem(
                description="Cable 100m",
                unit="rollo",
                quantity=Decimal("5"),
                unit_price=Decimal("40000"),
            )
        ],
    )
    fake_service = FakeUnifiedService(
        result=DocumentAnalysisAndQuotationResult(
            analysis=expected_analysis,
            quotation=expected_quotation,
        )
    )

    use_case = UploadTenderChatDocumentUseCase(
        chat_repo=chat_repo,
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        quotation_repo=quotation_repo,
        matching_result_repo=matching_repo,
        unified_service=fake_service,
    )

    pdf_bytes = b"%PDF-1.4 sample file"
    result = await use_case.execute(
        tender_id=tender_id,
        user_id=user_id,
        file_name="bases_tecnicas.pdf",
        file_bytes=pdf_bytes,
    )

    # 1. Verifica compatibilidad de tipo (es TenderChatDocument)
    assert isinstance(result, TenderChatDocument)
    assert isinstance(result, UploadTenderChatDocumentResult)
    assert result.file_name == "bases_tecnicas.pdf"
    assert result.file_type == "pdf"

    # 2. Verifica que se invocó el servicio unificado exactamente 1 vez
    assert fake_service.call_count == 1
    assert fake_service.last_kwargs["matching_score"] == 85.0

    # 3. Verifica persistencia en repo de licitaciones (DeepAnalysis)
    saved_analysis = await tender_repo.get_deep_analysis(tender_id, supplier.id)
    assert saved_analysis is not None
    assert saved_analysis.compatibility_score == 85.0
    assert saved_analysis.recommendation == "Postular"
    assert result.deep_analysis is not None
    assert result.deep_analysis.compatibility_score == 85.0

    # 4. Verifica persistencia en repo de cotizaciones (Quotation)
    saved_quotation = await quotation_repo.get(supplier.id, tender_id)
    assert saved_quotation is not None
    assert saved_quotation.currency == "CLP"
    assert len(saved_quotation.items) == 1
    assert saved_quotation.items[0].description == "Cable 100m"
    assert saved_quotation.total == Decimal("200000.00")
    assert result.quotation is not None
    assert result.quotation.total == Decimal("200000.00")


@pytest.mark.asyncio
async def test_upload_document_without_supplier_saves_document_gracefully(
    chat_repo, supplier_repo, tender_repo, quotation_repo, matching_repo
):
    user_id = uuid4()
    tender_id = uuid4()
    tender = create_tender(tender_id)
    tender_repo.tenders[tender_id] = tender

    fake_service = FakeUnifiedService()
    use_case = UploadTenderChatDocumentUseCase(
        chat_repo=chat_repo,
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        quotation_repo=quotation_repo,
        matching_result_repo=matching_repo,
        unified_service=fake_service,
    )

    result = await use_case.execute(
        tender_id=tender_id,
        user_id=user_id,
        file_name="bases.pdf",
        file_bytes=b"%PDF-1.4 file",
    )

    # El documento se guardó exitosamente
    assert result.file_name == "bases.pdf"
    assert fake_service.call_count == 0
    assert result.deep_analysis is None
    assert result.quotation is None


@pytest.mark.asyncio
async def test_upload_document_when_unified_service_fails_saves_document_gracefully(
    chat_repo, supplier_repo, tender_repo, quotation_repo, matching_repo
):
    user_id = uuid4()
    tender_id = uuid4()
    supplier = create_supplier(user_id)
    tender = create_tender(tender_id)

    await supplier_repo.save(supplier)
    tender_repo.tenders[tender_id] = tender

    fake_service = FakeUnifiedService(
        raise_error=DocumentAnalysisAndQuotationServiceError("Gemini rate limit exceeded")
    )
    use_case = UploadTenderChatDocumentUseCase(
        chat_repo=chat_repo,
        supplier_repo=supplier_repo,
        tender_repo=tender_repo,
        quotation_repo=quotation_repo,
        matching_result_repo=matching_repo,
        unified_service=fake_service,
    )

    result = await use_case.execute(
        tender_id=tender_id,
        user_id=user_id,
        file_name="bases.pdf",
        file_bytes=b"%PDF-1.4 file",
    )

    # Documento subido sin error fatal
    assert result.file_name == "bases.pdf"
    assert fake_service.call_count == 1
    assert result.deep_analysis is None
    assert result.quotation is None
