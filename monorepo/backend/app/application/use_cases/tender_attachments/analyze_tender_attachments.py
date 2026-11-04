import logging
from uuid import UUID

from app.application.repositories.attachment_file_repository import (
    IAttachmentFileRepository,
)
from app.application.repositories.matching_result_repository import (
    IMatchingResultRepository,
)
from app.application.repositories.quotation_repository import IQuotationRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_attachment_repository import (
    ITenderAttachmentRepository,
)
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.services.anexos_visibles import anexos_visibles
from app.application.services.attachment_storage import IAttachmentStorage
from app.application.services.document_analysis_quotation_service import (
    DocumentAnalysisAndQuotationResult,
    IDocumentAnalysisAndQuotationService,
)
from app.application.services.tender_assistant_ai_service import DocumentContextDTO

logger = logging.getLogger(__name__)


class AnalyzeTenderAttachmentsUseCase:
    """Análisis profundo + cotización con todos los anexos que ve la empresa (plan 233).

    Se dispara al subir un anexo y corre en segundo plano. Una sola llamada a
    Gemini con todas las bases legibles, para que el resultado no dependa de cuál
    se subió primero.
    """

    def __init__(
        self,
        suppliers: ISupplierRepository,
        tenders: ITenderRepository,
        files: IAttachmentFileRepository,
        attachments: ITenderAttachmentRepository,
        storage: IAttachmentStorage | None,
        matching_results: IMatchingResultRepository,
        quotations: IQuotationRepository,
        service: IDocumentAnalysisAndQuotationService,
    ) -> None:
        self.suppliers = suppliers
        self.tenders = tenders
        self.files = files
        self.attachments = attachments
        self.storage = storage
        self.matching_results = matching_results
        self.quotations = quotations
        self.service = service

    async def execute(
        self, workspace_id: UUID, tender_id: UUID
    ) -> DocumentAnalysisAndQuotationResult | None:
        """Devuelve `None` si no hay con qué analizar: sin empresa, licitación o anexos legibles."""
        empresa = await self.suppliers.get_by_id(workspace_id)
        if empresa is None:
            logger.info("Sin empresa %s: no se analizan los anexos.", workspace_id)
            return None
        licitaciones = await self.tenders.get_tenders(TenderFilters(ids=[tender_id]))
        if not licitaciones:
            logger.warning("Licitación %s no encontrada: no se analizan sus anexos.", tender_id)
            return None
        licitacion = licitaciones[0]

        documentos = await self._documentos(workspace_id, tender_id)
        if not documentos:
            return None

        puntaje: float | None = None
        fila = await self.matching_results.get_by_proveedor_and_licitacion(
            proveedor_id=empresa.id, licitacion_id=licitacion.id
        )
        if fila is not None and fila.final_score is not None:
            puntaje = fila.final_score * 100.0

        resultado = await self.service.analyze_and_quote(
            documents=documentos,
            tender=licitacion,
            supplier=empresa,
            matching_score=puntaje,
        )

        await self.tenders.save_deep_analysis(resultado.analysis)
        # Hay una sola cotización por empresa y licitación, y el usuario la edita
        # en la postulación: la de la IA solo llena una vacía, nunca la reemplaza.
        if await self.quotations.get(empresa.id, licitacion.id) is None:
            await self.quotations.save(
                supplier_id=empresa.id, tender_id=licitacion.id, data=resultado.quotation
            )
        return resultado

    async def _documentos(self, workspace_id: UUID, tender_id: UUID) -> list[DocumentContextDTO]:
        if self.storage is None:
            return []
        documentos: list[DocumentContextDTO] = []
        for anexo in await anexos_visibles(
            self.files, self.attachments, tender_id=tender_id, workspace_id=workspace_id
        ):
            if not anexo.legible:
                continue
            try:
                contenido = await self.storage.get_bytes(anexo.archivo.storage_key)
            except Exception:
                logger.warning(
                    "No se pudo leer el anexo %s para el análisis.", anexo.archivo.id, exc_info=True
                )
                continue
            documentos.append(
                DocumentContextDTO(
                    document_name=anexo.nombre, file_type=anexo.tipo, file_bytes=contenido
                )
            )
        return documentos
