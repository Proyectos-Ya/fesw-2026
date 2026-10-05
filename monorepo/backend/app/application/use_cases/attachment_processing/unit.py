"""Unidad de trabajo para el procesamiento de anexos (plan 233, decisión 4)."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass

from app.application.repositories.attachment_extraction_repository import (
    IAttachmentExtractionRepository,
)
from app.application.repositories.attachment_file_repository import (
    IAttachmentFileRepository,
)
from app.application.repositories.attachment_processing_job_repository import (
    IAttachmentProcessingJobRepository,
)
from app.application.repositories.gemini_usage_repository import (
    IGeminiUsageRepository,
)
from app.application.repositories.tender_attachment_repository import (
    ITenderAttachmentRepository,
)
from app.application.repositories.tender_digest_repository import (
    ITenderDigestRepository,
)
from app.application.repositories.tender_repository import ITenderRepository


@dataclass(frozen=True)
class AttachmentProcessingUnit:
    files: IAttachmentFileRepository
    attachments: ITenderAttachmentRepository
    tenders: ITenderRepository
    extractions: IAttachmentExtractionRepository
    digests: ITenderDigestRepository
    jobs: IAttachmentProcessingJobRepository
    usage: IGeminiUsageRepository


UnitFactory = Callable[[], AbstractAsyncContextManager[AttachmentProcessingUnit]]
