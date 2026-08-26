from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

MAX_DOCUMENT_SIZE_BYTES = 100 * 1024 * 1024


class DocumentStatus(StrEnum):
    PENDING_UPLOAD = "pending_upload"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255, pattern=r"(?i)^.+\.pdf$")
    content_type: Literal["application/pdf"]
    size_bytes: int = Field(gt=0, le=MAX_DOCUMENT_SIZE_BYTES)
    checksum_sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")


class DocumentUploadCreated(BaseModel):
    document_id: UUID
    status: Literal[DocumentStatus.PENDING_UPLOAD]
    upload_url: str


class DocumentJobAccepted(BaseModel):
    job_id: UUID
    document_id: UUID
    status: Literal[DocumentStatus.QUEUED]
    progress: int = 0


class MockExtractionResult(BaseModel):
    rut: str
    valid_until: str
    document_type: str
    confidence: float = Field(ge=0, le=1)


class DocumentProcessingError(BaseModel):
    code: str
    message: str


class DocumentJobStatus(BaseModel):
    job_id: UUID
    document_id: UUID
    status: DocumentStatus
    progress: int = Field(ge=0, le=100)
    result: MockExtractionResult | None = None
    error: DocumentProcessingError | None = None
