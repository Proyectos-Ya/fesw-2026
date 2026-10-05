import logging
import os
from typing import Optional
from uuid import UUID, uuid4

from app.application.repositories.matching_result_repository import (
    IMatchingResultRepository,
)
from app.application.repositories.quotation_repository import IQuotationRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_chat_repository import ITenderChatRepository
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.services.document_analysis_quotation_service import (
    IDocumentAnalysisAndQuotationService,
)
from app.application.services.document_validator_service import IDocumentValidatorService
from app.application.use_cases.supplier.resolver_empresa import resolver_empresa
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.quotation import Quotation
from app.domain.entities.tender_chat import TenderChatDocument
from app.domain.errors.tender_chat_errors import (
    MaxDocumentsExceededError,
    UnsupportedDocumentTypeError,
)

logger = logging.getLogger(__name__)


class UploadTenderChatDocumentResult(TenderChatDocument):
    """Resultado enriquecido que contiene el documento guardado y opcionalmente el análisis y cotización."""

    deep_analysis: Optional[DeepAnalysis] = None
    quotation: Optional[Quotation] = None


class UploadTenderChatDocumentUseCase:
    """Caso de uso para subir y validar documentos adjuntos al chat de una licitación,

    y opcionalmente generar en una sola llamada a Gemini el análisis profundo y la cotización estimada.
    """

    ALLOWED_EXTENSIONS = {"pdf", "xlsx", "png"}
    MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB
    MAX_DOCUMENTS_PER_CHAT = 10

    def __init__(
        self,
        chat_repo: ITenderChatRepository,
        validator_service: Optional[IDocumentValidatorService] = None,
        supplier_repo: Optional[ISupplierRepository] = None,
        tender_repo: Optional[ITenderRepository] = None,
        quotation_repo: Optional[IQuotationRepository] = None,
        matching_result_repo: Optional[IMatchingResultRepository] = None,
        unified_service: Optional[IDocumentAnalysisAndQuotationService] = None,
    ):
        self.chat_repo = chat_repo
        self.validator_service = validator_service
        self.supplier_repo = supplier_repo
        self.tender_repo = tender_repo
        self.quotation_repo = quotation_repo
        self.matching_result_repo = matching_result_repo
        self.unified_service = unified_service

    async def execute(
        self,
        tender_id: UUID,
        user_id: UUID,
        file_name: str,
        file_bytes: bytes,
        file_type: Optional[str] = None,
        supplier_id: Optional[UUID] = None,
    ) -> UploadTenderChatDocumentResult:
        # 1. Validar tamaño del archivo
        if not file_bytes or len(file_bytes) == 0:
            raise ValueError("El archivo está vacío.")

        if len(file_bytes) > self.MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"El archivo excede el tamaño máximo permitido de {self.MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB."
            )

        # 2. Validar extensión de archivo
        detected_type = file_type
        if not detected_type:
            if "." in file_name:
                detected_type = file_name.rsplit(".", 1)[-1].lower()
            else:
                detected_type = ""

        detected_type = detected_type.lower().strip()
        if detected_type not in self.ALLOWED_EXTENSIONS:
            raise UnsupportedDocumentTypeError()

        # 3. Validar límite de documentos por chat
        existing_docs = await self.chat_repo.get_documents_by_chat(user_id=user_id, tender_id=tender_id)
        if len(existing_docs) >= self.MAX_DOCUMENTS_PER_CHAT:
            raise MaxDocumentsExceededError(
                f"Se ha alcanzado el límite máximo de {self.MAX_DOCUMENTS_PER_CHAT} documentos adjuntos por chat."
            )

        # 4. Construir ruta de almacenamiento y entidad
        doc_id = uuid4()
        safe_name = os.path.basename(file_name)
        storage_path = f"uploads/{tender_id}/{user_id}/{doc_id}_{safe_name}"

        doc = TenderChatDocument(
            id=doc_id,
            tender_id=tender_id,
            user_id=user_id,
            file_name=safe_name,
            file_type=detected_type,  # type: ignore[arg-type]
            file_size_bytes=len(file_bytes),
            storage_path=storage_path,
        )

        # 5. Persistir documento
        saved_doc = await self.chat_repo.save_document(doc=doc, file_bytes=file_bytes)

        # 6. Generar análisis profundo y cotización estimada si los servicios están configurados
        if (
            self.unified_service is None
            or self.tender_repo is None
            or self.supplier_repo is None
            or self.quotation_repo is None
        ):
            return UploadTenderChatDocumentResult(
                **saved_doc.model_dump(),
                deep_analysis=None,
                quotation=None,
            )

        # Resolver proveedor activo o propio
        supplier = await resolver_empresa(self.supplier_repo, user_id, supplier_id)
        if not supplier:
            logger.info(
                "Usuario %s no tiene proveedor configurado. Omitiendo análisis y cotización automáticos.",
                user_id,
            )
            return UploadTenderChatDocumentResult(
                **saved_doc.model_dump(),
                deep_analysis=None,
                quotation=None,
            )

        # Resolver licitación
        tenders = await self.tender_repo.get_tenders(TenderFilters(ids=[tender_id]))
        if not tenders:
            logger.warning(
                "Licitación %s no encontrada en tender_repo. Omitiendo análisis y cotización.",
                tender_id,
            )
            return UploadTenderChatDocumentResult(
                **saved_doc.model_dump(),
                deep_analysis=None,
                quotation=None,
            )
        tender = tenders[0]

        # Resolver matching score si existe
        matching_score: Optional[float] = None
        if self.matching_result_repo is not None:
            matching_row = await self.matching_result_repo.get_by_proveedor_and_licitacion(
                proveedor_id=supplier.id,
                licitacion_id=tender.id,
            )
            if matching_row and matching_row.final_score is not None:
                matching_score = matching_row.final_score * 100.0

        # Invocar servicio unificado y persistir ambos resultados
        try:
            unified_result = await self.unified_service.analyze_and_quote(
                document_bytes=file_bytes,
                file_name=saved_doc.file_name,
                file_type=saved_doc.file_type,
                tender=tender,
                supplier=supplier,
                matching_score=matching_score,
            )

            # Persistir DeepAnalysis y Quotation
            saved_analysis = await self.tender_repo.save_deep_analysis(unified_result.analysis)
            saved_quotation = await self.quotation_repo.save(
                supplier_id=supplier.id,
                tender_id=tender.id,
                data=unified_result.quotation,
            )

            return UploadTenderChatDocumentResult(
                **saved_doc.model_dump(),
                deep_analysis=saved_analysis,
                quotation=saved_quotation,
            )
        except Exception as e:
            logger.warning(
                "Fallo al generar análisis y cotización unificados para licitación %s y doc %s: %s",
                tender_id,
                saved_doc.file_name,
                e,
                exc_info=True,
            )
            return UploadTenderChatDocumentResult(
                **saved_doc.model_dump(),
                deep_analysis=None,
                quotation=None,
            )
