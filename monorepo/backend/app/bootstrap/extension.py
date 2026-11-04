"""Providers de la extensión de navegador (plan 233, decisión 7)."""

from typing import Annotated

from fastapi import Depends

from app.application.use_cases.extension import (
    CheckExtensionAttachmentsUseCase,
    GetExtensionCapabilitiesUseCase,
    LeaseFetchJobsUseCase,
    PairExtensionUseCase,
    ReportJobResultUseCase,
)
from app.bootstrap.repositories import (
    AttachmentFileRepoDep,
    ExtensionFetchJobRepoDep,
    ExtensionInstallationRepoDep,
    TenderAttachmentRepoDep,
)
from app.config import settings


def get_extension_capabilities_use_case() -> GetExtensionCapabilitiesUseCase:
    return GetExtensionCapabilitiesUseCase(settings=settings)


def get_pair_extension_use_case(
    installation_repo: ExtensionInstallationRepoDep,
    capabilities_use_case: Annotated[
        GetExtensionCapabilitiesUseCase, Depends(get_extension_capabilities_use_case)
    ],
) -> PairExtensionUseCase:
    return PairExtensionUseCase(
        installation_repo=installation_repo,
        capabilities_use_case=capabilities_use_case,
    )


def get_check_extension_attachments_use_case(
    tender_attachment_repo: TenderAttachmentRepoDep,
    attachment_file_repo: AttachmentFileRepoDep,
) -> CheckExtensionAttachmentsUseCase:
    return CheckExtensionAttachmentsUseCase(
        tender_attachment_repo=tender_attachment_repo,
        attachment_file_repo=attachment_file_repo,
    )


def get_lease_extension_jobs_use_case(
    installation_repo: ExtensionInstallationRepoDep,
    job_repo: ExtensionFetchJobRepoDep,
) -> LeaseFetchJobsUseCase:
    return LeaseFetchJobsUseCase(
        installation_repo=installation_repo,
        job_repo=job_repo,
        max_daily_fetches=settings.extension_max_daily_fetches,
        lease_duration_seconds=settings.extension_polling_interval_seconds,
    )


def get_report_extension_job_result_use_case(
    job_repo: ExtensionFetchJobRepoDep,
) -> ReportJobResultUseCase:
    return ReportJobResultUseCase(job_repo=job_repo)
