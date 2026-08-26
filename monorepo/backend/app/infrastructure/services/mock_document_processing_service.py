import asyncio
import hashlib
from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

from app.application.schemas.document_processing_schema import (
    DocumentJobAccepted,
    DocumentJobStatus,
    DocumentProcessingError,
    DocumentStatus,
    DocumentUploadCreated,
    DocumentUploadRequest,
    MockExtractionResult,
)
from app.application.services.document_processing_service import (
    DocumentJobNotFound,
    DocumentNotFound,
    DocumentNotUploaded,
    DocumentUploadInvalid,
    IDocumentProcessingService,
)


@dataclass
class _StoredDocument:
    owner_id: UUID
    metadata: DocumentUploadRequest
    uploaded: bool = False


@dataclass
class _StoredJob:
    owner_id: UUID
    document_id: UUID
    outcome: Literal["completed", "failed"]
    polls: int = 0


class MockDocumentProcessingService(IDocumentProcessingService):
    """Mock en memoria que reproduce el contrato asíncrono sin ejecutar OCR.

    El estado avanza con cada consulta para que las pruebas y el frontend sean
    deterministas y no dependan de temporizadores ni de un worker real.
    """

    def __init__(self) -> None:
        self._documents: dict[UUID, _StoredDocument] = {}
        self._jobs: dict[UUID, _StoredJob] = {}
        self._lock = asyncio.Lock()

    async def create_upload(
        self, user_id: UUID, request: DocumentUploadRequest
    ) -> DocumentUploadCreated:
        document_id = uuid4()
        async with self._lock:
            self._documents[document_id] = _StoredDocument(user_id, request)
        return DocumentUploadCreated(
            document_id=document_id,
            status=DocumentStatus.PENDING_UPLOAD,
            upload_url=f"/document-uploads/{document_id}/content",
        )

    async def store_content(
        self, user_id: UUID, document_id: UUID, content: bytes
    ) -> None:
        async with self._lock:
            document = self._owned_document(user_id, document_id)
            if not content.startswith(b"%PDF"):
                raise DocumentUploadInvalid(
                    "El contenido no tiene una cabecera PDF válida"
                )
            if len(content) != document.metadata.size_bytes:
                raise DocumentUploadInvalid("El tamaño no coincide con los metadatos")
            expected = document.metadata.checksum_sha256
            if (
                expected
                and hashlib.sha256(content).hexdigest().lower() != expected.lower()
            ):
                raise DocumentUploadInvalid("El checksum SHA-256 no coincide")
            document.uploaded = True

    async def start_processing(
        self,
        user_id: UUID,
        document_id: UUID,
        outcome: Literal["completed", "failed"],
    ) -> DocumentJobAccepted:
        async with self._lock:
            document = self._owned_document(user_id, document_id)
            if not document.uploaded:
                raise DocumentNotUploaded("El PDF todavía no fue cargado")
            job_id = uuid4()
            self._jobs[job_id] = _StoredJob(user_id, document_id, outcome)
        return DocumentJobAccepted(
            job_id=job_id,
            document_id=document_id,
            status=DocumentStatus.QUEUED,
            progress=0,
        )

    async def get_job(self, user_id: UUID, job_id: UUID) -> DocumentJobStatus:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.owner_id != user_id:
                raise DocumentJobNotFound("Trabajo no encontrado")
            job.polls += 1

            if job.polls == 1:
                return DocumentJobStatus(
                    job_id=job_id,
                    document_id=job.document_id,
                    status=DocumentStatus.PROCESSING,
                    progress=50,
                )
            if job.outcome == "failed":
                return DocumentJobStatus(
                    job_id=job_id,
                    document_id=job.document_id,
                    status=DocumentStatus.FAILED,
                    progress=100,
                    error=DocumentProcessingError(
                        code="ocr_low_confidence",
                        message="No fue posible extraer datos con confianza suficiente",
                    ),
                )
            return DocumentJobStatus(
                job_id=job_id,
                document_id=job.document_id,
                status=DocumentStatus.COMPLETED,
                progress=100,
                result=MockExtractionResult(
                    rut="76.123.456-7",
                    valid_until="2027-12-31",
                    document_type="certificado_vigencia",
                    confidence=0.97,
                ),
            )

    def _owned_document(self, user_id: UUID, document_id: UUID) -> _StoredDocument:
        document = self._documents.get(document_id)
        if document is None or document.owner_id != user_id:
            raise DocumentNotFound("Documento no encontrado")
        return document
