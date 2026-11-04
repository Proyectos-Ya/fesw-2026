"""Factoría de unidades de procesamiento SQL (plan 233, decisión 4)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.use_cases.attachment_processing.unit import (
    AttachmentProcessingUnit,
    UnitFactory,
)
from app.infrastructure.repositories.sql_attachment_extraction_repository import (
    SqlAttachmentExtractionRepository,
)
from app.infrastructure.repositories.sql_attachment_file_repository import (
    SqlAttachmentFileRepository,
)
from app.infrastructure.repositories.sql_attachment_processing_job_repository import (
    SqlAttachmentProcessingJobRepository,
)
from app.infrastructure.repositories.sql_gemini_usage_repository import (
    SqlGeminiUsageRepository,
)
from app.infrastructure.repositories.sql_tender_attachment_repository import (
    SqlTenderAttachmentRepository,
)
from app.infrastructure.repositories.sql_tender_digest_repository import (
    SqlTenderDigestRepository,
)
from app.infrastructure.repositories.tender_repository import TenderRepository


def sql_processing_units(
    session_maker: async_sessionmaker[AsyncSession],
) -> UnitFactory:
    @asynccontextmanager
    async def unidad() -> AsyncIterator[AttachmentProcessingUnit]:
        async with session_maker() as session:
            yield AttachmentProcessingUnit(
                files=SqlAttachmentFileRepository(session),
                attachments=SqlTenderAttachmentRepository(session),
                tenders=TenderRepository(session),
                extractions=SqlAttachmentExtractionRepository(session),
                digests=SqlTenderDigestRepository(session),
                jobs=SqlAttachmentProcessingJobRepository(session),
                usage=SqlGeminiUsageRepository(session),
            )

    return unidad
