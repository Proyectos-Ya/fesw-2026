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
from app.domain.entities.supplier_member import WorkspaceContext
from app.domain.entities.user import User
from app.domain.errors.tender_errors import TenderNotFound


def create_quotation_router(
    get_current_user: Callable,
    get_quotation_use_case: Callable,
    get_current_workspace_context: Callable | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/tenders", tags=["Quotations"])
    workspace_context_dep = get_current_workspace_context or (lambda: None)

    def _empresa_activa(workspace_context: WorkspaceContext | None) -> UUID | None:
        return workspace_context.active_supplier_id if workspace_context else None

    @router.get("/{tender_id}/quotation", response_model=Quotation)
    async def get_quotation(
        tender_id: UUID,
        user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[QuotationUseCase, Depends(get_quotation_use_case)],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
    ):
        try:
            return await use_case.get(
                user.id, tender_id, supplier_id=_empresa_activa(workspace_context)
            )
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
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
    ):
        try:
            return await use_case.save(
                user.id,
                tender_id,
                data,
                supplier_id=_empresa_activa(workspace_context),
            )
        except QuotationCompanyRequired as error:
            raise HTTPException(403, str(error)) from error
        except TenderNotFound as error:
            raise HTTPException(404, str(error)) from error

    return router
