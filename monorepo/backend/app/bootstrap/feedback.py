from typing import Annotated

from fastapi import Depends

from app.application.use_cases.feedback.report_match import ReportMatchUseCase
from app.bootstrap.repositories import (
    MatchReportRepoDep,
    SupplierRepoDep,
    TenderRepoDep,
)


def get_report_match_use_case(
    match_report_repo: MatchReportRepoDep,
    tender_repo: TenderRepoDep,
    supplier_repo: SupplierRepoDep,
) -> ReportMatchUseCase:
    return ReportMatchUseCase(
        match_report_repo=match_report_repo,
        tender_repo=tender_repo,
        supplier_repo=supplier_repo,
    )


ReportMatchUseCaseDep = Annotated[
    ReportMatchUseCase, Depends(get_report_match_use_case)
]
