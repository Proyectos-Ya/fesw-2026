"""Análisis profundo + cotización con los anexos que ve la empresa (plan 233)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.application.services.document_analysis_quotation_service import (
    DocumentAnalysisAndQuotationResult,
    IDocumentAnalysisAndQuotationService,
)
from app.application.use_cases.tender_attachments.analyze_tender_attachments import (
    AnalyzeTenderAttachmentsUseCase,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
)
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.matching_result import MatchingResult
from app.domain.entities.quotation import MaterialItem, Quotation, QuotationInput
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender
from app.domain.errors.document_analysis_quotation_errors import (
    DocumentAnalysisAndQuotationServiceError,
)
from app.shared.datetime_utils import utc_now_naive
from tests.unit.application.attachment_fakes import InMemoryTenderAttachmentRepository
from tests.unit.application.attachment_file_fakes import (
    FakeAttachmentStorage,
    InMemoryAttachmentFileRepository,
)
from tests.unit.application.fakes import (
    InMemoryMatchingResultRepository,
    InMemorySupplierRepository,
    InMemoryTenderRepository,
)


class FakeQuotationRepository:
    def __init__(self) -> None:
        self.quotations: dict[tuple[UUID, UUID], Quotation] = {}

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
    def __init__(self, result=None, raise_error: Exception | None = None) -> None:
        self.result = result
        self.raise_error = raise_error
        self.llamadas: list[dict] = []

    async def analyze_and_quote(self, documents, tender, supplier, matching_score=None):
        self.llamadas.append(
            {"documents": documents, "tender": tender, "supplier": supplier, "score": matching_score}
        )
        if self.raise_error:
            raise self.raise_error
        return self.result


def _cotizacion(descripcion: str) -> QuotationInput:
    return QuotationInput(
        currency="CLP",
        items=[
            MaterialItem(
                description=descripcion,
                unit="unidad",
                quantity=Decimal("2"),
                unit_price=Decimal("5000"),
            )
        ],
    )


class Escenario:
    def __init__(self, raise_error: Exception | None = None) -> None:
        ahora = datetime.now(UTC).replace(tzinfo=None)
        self.tender = Tender(
            code="LIC-1",
            name="Cables de cobre",
            status_id=5,
            published_at=ahora - timedelta(days=1),
            closing_at=ahora + timedelta(days=5),
            last_change_at=ahora,
            buyer_rut="11.111.111-1",
            buyer_unit="Compras",
        )
        self.empresa = Supplier(
            id=uuid4(),
            user_id=uuid4(),
            rut="22.222.222-2",
            legal_name="Electro S.A.",
            trade_name="Electro",
            description="Fábrica de conductores",
        )
        self.empresas = InMemorySupplierRepository()
        self.tenders = InMemoryTenderRepository()
        self.tenders.tenders[self.tender.id] = self.tender
        self.archivos = InMemoryAttachmentFileRepository()
        self.oficiales = InMemoryTenderAttachmentRepository()
        self.almacen = FakeAttachmentStorage()
        self.matching = InMemoryMatchingResultRepository()
        self.cotizaciones = FakeQuotationRepository()
        self.servicio = FakeUnifiedService(
            result=DocumentAnalysisAndQuotationResult(
                analysis=DeepAnalysis(
                    id=uuid4(),
                    tender_id=self.tender.id,
                    supplier_id=self.empresa.id,
                    compatibility_score=85.0,
                    recommendation="Postular",
                    justification="Calza con el rubro.",
                ),
                quotation=_cotizacion("Sugerencia de la IA"),
            ),
            raise_error=raise_error,
        )
        self.use_case = AnalyzeTenderAttachmentsUseCase(
            suppliers=self.empresas,
            tenders=self.tenders,
            files=self.archivos,
            attachments=self.oficiales,
            storage=self.almacen,
            matching_results=self.matching,
            quotations=self.cotizaciones,
            service=self.servicio,
        )

    async def con_empresa(self) -> "Escenario":
        await self.empresas.save(self.empresa)
        return self

    async def subir(self, nombre: str, workspace_id: UUID | None = None, contenido: bytes = b"%PDF") -> None:
        oficial = await self.oficiales.create_attachment(self.tender.id, uuid4(), nombre)
        archivo = AttachmentFile(
            id=uuid4(),
            tender_attachment_id=oficial.id,
            tender_id=self.tender.id,
            sha256=uuid4().hex * 2,
            size_bytes=len(contenido),
            storage_key=f"anexos/{uuid4()}",
            source=AttachmentFileSource.MANUAL,
            uploader_user_id=uuid4(),
            workspace_id=workspace_id or self.empresa.id,
            status=AttachmentFileStatus.STORED,
            created_at=utc_now_naive(),
        )
        self.archivos.filas[archivo.id] = archivo
        self.almacen.subir(archivo.storage_key, contenido)

    async def analizar(self):
        return await self.use_case.execute(self.empresa.id, self.tender.id)


async def test_analiza_con_todos_los_anexos_visibles_en_una_llamada():
    escenario = await Escenario().con_empresa()
    await escenario.subir("bases-administrativas.pdf")
    await escenario.subir("bases-tecnicas.pdf")
    await escenario.subir("de-otra-empresa.pdf", workspace_id=uuid4())

    await escenario.analizar()

    [llamada] = escenario.servicio.llamadas
    assert sorted(d.document_name for d in llamada["documents"]) == [
        "bases-administrativas.pdf",
        "bases-tecnicas.pdf",
    ]
    assert llamada["supplier"].id == escenario.empresa.id


async def test_los_tipos_que_la_ia_no_lee_no_se_mandan():
    escenario = await Escenario().con_empresa()
    await escenario.subir("bases.pdf")
    await escenario.subir("formulario.docx")

    await escenario.analizar()

    [llamada] = escenario.servicio.llamadas
    assert [d.document_name for d in llamada["documents"]] == ["bases.pdf"]


async def test_usa_el_puntaje_de_matching_si_existe():
    escenario = await Escenario().con_empresa()
    await escenario.subir("bases.pdf")
    await escenario.matching.save_on_demand(
        MatchingResult(
            id=uuid4(),
            supplier_id=escenario.empresa.id,
            tender_id=escenario.tender.id,
            final_score=0.85,
            model_version="v1",
            calculated_at=utc_now_naive(),
        )
    )

    await escenario.analizar()

    assert escenario.servicio.llamadas[0]["score"] == 85.0


async def test_guarda_el_analisis_y_la_cotizacion_si_no_habia():
    escenario = await Escenario().con_empresa()
    await escenario.subir("bases.pdf")

    await escenario.analizar()

    analisis = await escenario.tenders.get_deep_analysis(escenario.tender.id, escenario.empresa.id)
    assert analisis is not None and analisis.recommendation == "Postular"
    cotizacion = await escenario.cotizaciones.get(escenario.empresa.id, escenario.tender.id)
    assert [i.description for i in cotizacion.items] == ["Sugerencia de la IA"]


async def test_no_pisa_una_cotizacion_que_ya_existe():
    # Una sola cotización por empresa y licitación, y el usuario la edita en la
    # postulación: la de la IA solo llena una vacía.
    escenario = await Escenario().con_empresa()
    await escenario.subir("bases.pdf")
    del_usuario = await escenario.cotizaciones.save(
        escenario.empresa.id, escenario.tender.id, _cotizacion("Armada a mano")
    )

    await escenario.analizar()

    guardada = await escenario.cotizaciones.get(escenario.empresa.id, escenario.tender.id)
    assert guardada is del_usuario


async def test_sin_anexos_legibles_no_llama_a_la_ia():
    escenario = await Escenario().con_empresa()
    await escenario.subir("formulario.docx")

    assert await escenario.analizar() is None
    assert escenario.servicio.llamadas == []


async def test_sin_empresa_no_llama_a_la_ia():
    escenario = Escenario()
    await escenario.subir("bases.pdf")

    assert await escenario.analizar() is None
    assert escenario.servicio.llamadas == []


async def test_si_la_ia_falla_el_error_sube_y_no_guarda_nada():
    # Corre en segundo plano: quien lo agenda registra el error.
    escenario = await Escenario(
        raise_error=DocumentAnalysisAndQuotationServiceError("Gemini caído")
    ).con_empresa()
    await escenario.subir("bases.pdf")

    with pytest.raises(DocumentAnalysisAndQuotationServiceError):
        await escenario.analizar()

    assert await escenario.cotizaciones.get(escenario.empresa.id, escenario.tender.id) is None
