"""Providers de anexos oficiales: lista, subida manual, promoción y resumen (plan 233)."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.attachment_processing_job_repository import (
    IAttachmentProcessingJobRepository,
)
from app.application.repositories.attachment_processing_status_reader import (
    IAttachmentProcessingStatusReader,
)
from app.application.services.attachment_deleted_listener import (
    CompositeAttachmentDeletedListener,
    IAttachmentDeletedListener,
)
from app.application.services.attachment_processing_notifier import (
    IAttachmentProcessingNotifier,
)
from app.application.services.attachment_storage import IAttachmentStorage
from app.application.services.attachment_stored_listener import (
    CompositeAttachmentStoredListener,
    IAttachmentStoredListener,
)
from app.application.services.attachment_visibility_listener import (
    IAttachmentVisibilityListener,
    NoopAttachmentVisibilityListener,
)
from app.application.services.enqueue_extraction_listener import (
    EnqueueExtractionOnStored,
)
from app.application.services.milestone_extraction_background import (
    IMilestoneExtractionBackground,
)
from app.application.services.schedule_ai_on_stored import (
    ScheduleMilestonesOnStored,
    ScheduleTenderAnalysisOnStored,
)
from app.application.services.tender_analysis_background import (
    ITenderAnalysisBackground,
)
from app.application.use_cases.attachment_processing.build_tender_digest import (
    BuildTenderDigestUseCase,
)
from app.application.use_cases.attachment_processing.get_tender_digest import (
    GetTenderDigestUseCase,
)
from app.application.use_cases.tender_attachments.complete_attachment_upload import (
    CompleteAttachmentUploadUseCase,
)
from app.application.use_cases.tender_attachments.delete_attachment_file import (
    DeleteAttachmentFileUseCase,
)
from app.application.use_cases.tender_attachments.get_tender_attachments import (
    GetTenderAttachmentsUseCase,
)
from app.application.use_cases.tender_attachments.promote_attachment import (
    AttachmentPromotionListener,
    PromoteAttachmentUseCase,
    PromoteOpener,
)
from app.application.use_cases.tender_attachments.request_attachment_upload import (
    RequestAttachmentUploadUseCase,
)
from app.bootstrap.repositories import (
    AttachmentExtractionRepoDep,
    AttachmentFileRepoDep,
    TenderAttachmentRepoDep,
    TenderDigestRepoDep,
    TenderRepoDep,
    get_attachment_processing_job_repo,
    get_attachment_processing_status_reader,
)
from app.bootstrap.services import (
    AttachmentStorageDep,
    get_attachment_processing_notifier,
    get_milestone_extraction_background,
    get_tender_analysis_background,
)
from app.config import settings
from app.infrastructure.db import async_session_maker
from app.infrastructure.repositories.sql_attachment_trust_repository import (
    SqlAttachmentTrustRepository,
)


def build_promotion_opener(
    storage: IAttachmentStorage | None,
    visibility_listener: IAttachmentVisibilityListener,
    session_factory: Callable[[], AsyncSession] = async_session_maker,
) -> PromoteOpener:
    """Entrega un caso de uso de promoción por evaluación, cada uno con su sesión.

    La promoción toma un candado sobre el anexo y hace su propio commit (decisión
    6): no puede usar la sesión de la petición, que puede traer cambios sin
    confirmar o quedar en un estado fallido por otro listener. Mismo patrón que
    `registrar_impresiones_de_ranking`.
    """

    @asynccontextmanager
    async def abrir() -> AsyncIterator[PromoteAttachmentUseCase]:
        async with session_factory() as session:
            yield PromoteAttachmentUseCase(
                trust=SqlAttachmentTrustRepository(session),
                storage=storage,
                visibility_listener=visibility_listener,
            )

    return abrir


def get_attachment_visibility_listener() -> IAttachmentVisibilityListener:
    # Decisión 4: reconstruir el resumen compartido cuando una versión entra o sale
    # de lo compartido. Hasta entonces, nadie escucha.
    return NoopAttachmentVisibilityListener()


def get_attachment_promotion_listener(
    storage: AttachmentStorageDep,
    visibility: Annotated[
        IAttachmentVisibilityListener, Depends(get_attachment_visibility_listener)
    ],
) -> AttachmentPromotionListener:
    return AttachmentPromotionListener(build_promotion_opener(storage, visibility))


AttachmentPromotionListenerDep = Annotated[
    AttachmentPromotionListener, Depends(get_attachment_promotion_listener)
]


def get_attachment_stored_listener(
    promotion: AttachmentPromotionListenerDep,
    jobs: Annotated[
        IAttachmentProcessingJobRepository | None,
        Depends(get_attachment_processing_job_repo),
    ] = None,
    notifier: Annotated[
        IAttachmentProcessingNotifier | None,
        Depends(get_attachment_processing_notifier),
    ] = None,
    milestones: Annotated[
        IMilestoneExtractionBackground | None,
        Depends(get_milestone_extraction_background),
    ] = None,
    analysis: Annotated[
        ITenderAnalysisBackground | None, Depends(get_tender_analysis_background)
    ] = None,
) -> IAttachmentStoredListener:
    # Decisión 6 (promoción), decisión 4 (extracción) y, al subir un anexo, los
    # hitos y el análisis + cotización (plan 233-disparar-ia-con-anexos).
    listeners: list[IAttachmentStoredListener] = [promotion]
    if jobs is not None and notifier is not None:
        listeners.append(EnqueueExtractionOnStored(jobs=jobs, notifier=notifier))
    if milestones is not None:
        listeners.append(ScheduleMilestonesOnStored(milestones))
    if analysis is not None:
        listeners.append(ScheduleTenderAnalysisOnStored(analysis))
    return CompositeAttachmentStoredListener(listeners)


def get_attachment_deleted_listener(
    promotion: AttachmentPromotionListenerDep,
) -> IAttachmentDeletedListener:
    return CompositeAttachmentDeletedListener([promotion])


AttachmentStoredListenerDep = Annotated[
    IAttachmentStoredListener, Depends(get_attachment_stored_listener)
]


AttachmentDeletedListenerDep = Annotated[
    IAttachmentDeletedListener, Depends(get_attachment_deleted_listener)
]


def get_tender_attachments_use_case(
    attachments: TenderAttachmentRepoDep,
    files: AttachmentFileRepoDep,
    storage: AttachmentStorageDep,
    status: Annotated[
        IAttachmentProcessingStatusReader | None,
        Depends(get_attachment_processing_status_reader),
    ] = None,
    analysis: Annotated[
        ITenderAnalysisBackground | None, Depends(get_tender_analysis_background)
    ] = None,
) -> GetTenderAttachmentsUseCase:
    return GetTenderAttachmentsUseCase(
        attachments,
        files,
        uploads_per_month=settings.attachment_manual_uploads_per_month,
        storage_available=storage is not None,
        processing=status,
        processing_enabled=settings.run_attachment_processing and storage is not None,
        analysis=analysis,
    )


def get_tender_digest_use_case(
    tenders: TenderRepoDep,
    extractions: AttachmentExtractionRepoDep,
    digests: TenderDigestRepoDep,
    status: Annotated[
        IAttachmentProcessingStatusReader,
        Depends(get_attachment_processing_status_reader),
    ],
) -> GetTenderDigestUseCase:
    return GetTenderDigestUseCase(
        tenders=tenders,
        extractions=extractions,
        status=status,
        build=BuildTenderDigestUseCase(
            tenders=tenders,
            extractions=extractions,
            digests=digests,
        ),
    )


def get_request_attachment_upload_use_case(
    attachments: TenderAttachmentRepoDep,
    files: AttachmentFileRepoDep,
    storage: AttachmentStorageDep,
    listener: AttachmentStoredListenerDep,
) -> RequestAttachmentUploadUseCase:
    return RequestAttachmentUploadUseCase(
        attachments=attachments,
        files=files,
        storage=storage,
        listener=listener,
        uploads_per_month=settings.attachment_manual_uploads_per_month,
    )


def get_complete_attachment_upload_use_case(
    files: AttachmentFileRepoDep,
    storage: AttachmentStorageDep,
    listener: AttachmentStoredListenerDep,
) -> CompleteAttachmentUploadUseCase:
    return CompleteAttachmentUploadUseCase(files=files, storage=storage, listener=listener)


def get_delete_attachment_file_use_case(
    files: AttachmentFileRepoDep,
    storage: AttachmentStorageDep,
    listener: AttachmentDeletedListenerDep,
) -> DeleteAttachmentFileUseCase:
    return DeleteAttachmentFileUseCase(files=files, storage=storage, listener=listener)
