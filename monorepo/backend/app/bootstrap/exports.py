"""Providers de exportaciones y enlaces compartidos (HdU 19)."""

from typing import Annotated

from fastapi import Depends

from app.application.services.export_background import IExportBackground
from app.application.use_cases.exports.build_export_snapshot import (
    BuildExportSnapshotUseCase,
)
from app.application.use_cases.exports.export_jobs import (
    DownloadExportFileUseCase,
    GetExportJobUseCase,
)
from app.application.use_cases.exports.export_tender import ExportTenderUseCase
from app.application.use_cases.sharing.tender_sharing import (
    CreateShareLinkUseCase,
    GetSharedTenderUseCase,
    ListShareLinksUseCase,
    RevokeShareLinkUseCase,
)
from app.bootstrap.repositories import (
    ExportJobRepoDep,
    MatchingResultRepoDep,
    QuotationRepoDep,
    SupplierRepoDep,
    TenderRepoDep,
    TenderShareLinkRepoDep,
)
from app.bootstrap.services import get_export_background
from app.config import settings
from app.infrastructure.services.exports.excel_renderer import OpenpyxlExcelRenderer
from app.infrastructure.services.exports.pdf_renderer import ReportLabPdfRenderer


def get_export_tender_use_case(
    tenders: TenderRepoDep,
    matching_results: MatchingResultRepoDep,
    quotations: QuotationRepoDep,
    jobs: ExportJobRepoDep,
    background: Annotated[IExportBackground, Depends(get_export_background)],
) -> ExportTenderUseCase:
    return ExportTenderUseCase(
        snapshots=BuildExportSnapshotUseCase(
            tenders=tenders, matching_results=matching_results, quotations=quotations
        ),
        jobs=jobs,
        pdf_renderer=ReportLabPdfRenderer(),
        excel_renderer=OpenpyxlExcelRenderer(),
        background=background,
        inline_timeout_seconds=settings.export_inline_timeout_seconds,
    )


def get_export_job_use_case(jobs: ExportJobRepoDep) -> GetExportJobUseCase:
    return GetExportJobUseCase(jobs)


def get_download_export_file_use_case(
    jobs: ExportJobRepoDep,
) -> DownloadExportFileUseCase:
    return DownloadExportFileUseCase(jobs)


def get_create_share_link_use_case(
    links: TenderShareLinkRepoDep,
    tenders: TenderRepoDep,
) -> CreateShareLinkUseCase:
    return CreateShareLinkUseCase(links=links, tenders=tenders, base_url=settings.app_base_url)


def get_list_share_links_use_case(links: TenderShareLinkRepoDep) -> ListShareLinksUseCase:
    return ListShareLinksUseCase(links=links)


def get_revoke_share_link_use_case(links: TenderShareLinkRepoDep) -> RevokeShareLinkUseCase:
    return RevokeShareLinkUseCase(links=links)


def get_shared_tender_use_case(
    links: TenderShareLinkRepoDep,
    tenders: TenderRepoDep,
    suppliers: SupplierRepoDep,
    matching_results: MatchingResultRepoDep,
) -> GetSharedTenderUseCase:
    return GetSharedTenderUseCase(
        links=links,
        tenders=tenders,
        suppliers=suppliers,
        matching_results=matching_results,
    )
