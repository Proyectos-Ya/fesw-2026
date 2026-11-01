from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.schemas.feedback_schema import (
    AppFeedbackResponse,
    CreateCommentRequest,
    CreateReviewRequest,
    MatchReportResponse,
    ReportMatchRequest,
)
from app.application.use_cases.feedback.report_match import ReportMatchUseCase
from app.application.use_cases.feedback.submit_app_feedback import (
    SubmitAppFeedbackUseCase,
)
from app.domain.entities.supplier_member import WorkspaceContext
from app.domain.entities.user import User
from app.domain.errors.supplier_errors import SupplierNotFoundForUser
from app.domain.errors.tender_errors import TenderNotFound


def create_feedback_router(
    get_current_user: Callable,
    get_report_match_use_case: Callable,
    get_submit_app_feedback_use_case: Callable | None = None,
    get_current_workspace_context: Callable | None = None,
) -> APIRouter:
    """Retroalimentación de la empresa sobre los resultados del sistema (HU-24)."""
    router = APIRouter(tags=["Feedback"], dependencies=[Depends(get_current_user)])
    workspace_dep = get_current_workspace_context or (lambda: None)

    @router.post(
        "/tenders/{tender_id}/reports",
        response_model=MatchReportResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Reportar un mal match o un análisis de compatibilidad incorrecto",
        responses={
            404: {"description": "La licitación o la empresa del usuario no existe"},
        },
    )
    async def report_match(
        tender_id: UUID,
        body: ReportMatchRequest,
        current_user: Annotated[User, Depends(get_current_user)],
        workspace_context: Annotated[WorkspaceContext | None, Depends(workspace_dep)],
        use_case: Annotated[ReportMatchUseCase, Depends(get_report_match_use_case)],
    ):
        """Guarda el motivo del descontento de la empresa activa.

        Con `kind=match` la licitación deja de recomendarse a esa empresa. Reportar
        de nuevo la misma licitación y tipo reemplaza el motivo anterior.
        """
        try:
            return await use_case.execute(
                user_id=current_user.id,
                supplier_id=(
                    workspace_context.active_supplier_id if workspace_context else None
                ),
                tender_id=tender_id,
                kind=body.kind,
                reason=body.reason,
            )
        except (TenderNotFound, SupplierNotFoundForUser) as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e


    @router.post(
        "/feedback/comments",
        response_model=AppFeedbackResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Dejar un mensaje, comentario o queja acerca del sistema (HU-24, S6)",
    )
    async def create_comment(
        body: CreateCommentRequest,
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            SubmitAppFeedbackUseCase,
            Depends(get_submit_app_feedback_use_case or (lambda: None)),
        ],
    ):
        """Permite a un usuario autenticado enviar comentarios, sugerencias o quejas desde ajustes."""
        return await use_case.submit_comment(
            user_id=current_user.id,
            message=body.message,
        )

    @router.post(
        "/feedback/reviews",
        response_model=AppFeedbackResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Dejar una reseña con estrellas y comentario opcional (HU-24, S7)",
    )
    async def create_review(
        body: CreateReviewRequest,
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            SubmitAppFeedbackUseCase,
            Depends(get_submit_app_feedback_use_case or (lambda: None)),
        ],
    ):
        """Permite a un usuario autenticado dejar una reseña (0 a 5 estrellas) con opción de anonimato."""
        return await use_case.submit_review(
            user_id=current_user.id,
            rating=body.rating,
            message=body.message,
            anonymous=body.anonymous,
        )

    return router
