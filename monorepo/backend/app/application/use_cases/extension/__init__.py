"""Casos de uso del módulo de extensión de navegador (Plan 233, Decisión 7)."""

from app.application.use_cases.extension.check_extension_attachments import (
    CheckExtensionAttachmentsUseCase,
)
from app.application.use_cases.extension.get_extension_capabilities import (
    GetExtensionCapabilitiesUseCase,
)
from app.application.use_cases.extension.lease_fetch_jobs import (
    LeaseFetchJobsUseCase,
)
from app.application.use_cases.extension.pair_extension import (
    PairExtensionUseCase,
)
from app.application.use_cases.extension.report_job_result import (
    ReportJobResultUseCase,
)

__all__ = [
    "CheckExtensionAttachmentsUseCase",
    "GetExtensionCapabilitiesUseCase",
    "LeaseFetchJobsUseCase",
    "PairExtensionUseCase",
    "ReportJobResultUseCase",
]
