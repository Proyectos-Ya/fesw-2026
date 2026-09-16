from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.application.use_cases.quotation import (
    QuotationCompanyRequired,
    QuotationNotFound,
    QuotationUseCase,
)
from app.domain.entities.quotation import Quotation, QuotationInput
from app.domain.entities.user import User
from app.domain.errors.tender_errors import TenderNotFound


def create_quotation_router(
    get_current_user: Callable, get_quotation_use_case: Callable
) -> APIRouter:
    router = APIRouter(prefix="/tenders", tags=["Quotations"])

    @router.get("/{tender_id}/quotation", response_model=Quotation)
    async def get_quotation(
        tender_id: UUID,
        user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[QuotationUseCase, Depends(get_quotation_use_case)],
    ):
        try:
            return await use_case.get(user.id, tender_id)
        except QuotationCompanyRequired as error:
            raise HTTPException(403, str(error)) from error
        except (QuotationNotFound, TenderNotFound) as error:
            raise HTTPException(404, str(error)) from error

    @router.put("/{tender_id}/quotation", response_model=Quotation)
    async def save_quotation(
        tender_id: UUID,
        data: QuotationInput,
        user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[QuotationUseCase, Depends(get_quotation_use_case)],
    ):
        try:
            return await use_case.save(user.id, tender_id, data)
        except QuotationCompanyRequired as error:
            raise HTTPException(403, str(error)) from error
        except TenderNotFound as error:
            raise HTTPException(404, str(error)) from error

    return router
