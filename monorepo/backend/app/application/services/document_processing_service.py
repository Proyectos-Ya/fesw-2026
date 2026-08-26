from abc import ABC, abstractmethod
from typing import Literal
from uuid import UUID

from app.application.schemas.document_processing_schema import (
    DocumentJobAccepted,
    DocumentJobStatus,
    DocumentUploadCreated,
    DocumentUploadRequest,
)


class DocumentNotFound(Exception):
    pass


class DocumentUploadInvalid(Exception):
    pass


class DocumentNotUploaded(Exception):
    pass


class DocumentJobNotFound(Exception):
    pass


class IDocumentProcessingService(ABC):
    @abstractmethod
    async def create_upload(
        self, user_id: UUID, request: DocumentUploadRequest
    ) -> DocumentUploadCreated: ...

    @abstractmethod
    async def store_content(
        self, user_id: UUID, document_id: UUID, content: bytes
    ) -> None: ...

    @abstractmethod
    async def start_processing(
        self,
        user_id: UUID,
        document_id: UUID,
        outcome: Literal["completed", "failed"],
    ) -> DocumentJobAccepted: ...

    @abstractmethod
    async def get_job(self, user_id: UUID, job_id: UUID) -> DocumentJobStatus: ...
