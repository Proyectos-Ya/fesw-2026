"""Postulación a una Compra Ágil: borrador de la empresa activa (HU-20).

B2 expone la factibilidad y la lectura del borrador. Responder, decidir ante una
discrepancia, reanudar, redactar y exportar llegan en las etapas siguientes.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.schemas.proposal_schema import ProposalDraftView
from app.application.services.proposal_ai_service import ProposalAIServiceError
from app.application.use_cases.proposals.get_proposal import GetProposalUseCase
from app.application.use_cases.proposals.start_feasibility import (
    StartFeasibilityUseCase,
)
from app.domain.entities.proposal import ProposalDraft
from app.domain.entities.supplier_member import WorkspaceContext
from app.domain.entities.user import User
from app.domain.errors.proposal_errors import ProposalDraftNotFound
from app.domain.errors.supplier_errors import SupplierNotFoundForUser
from app.domain.errors.tender_errors import TenderClosedForProposal, TenderNotFound

PERMISO_ESCRITURA = "generate_proposal"


def create_proposal_router(
    get_current_user: Callable,
    get_start_feasibility_use_case: Callable,
    get_proposal_use_case: Callable,
    get_current_workspace_context: Callable | None = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/tenders",
        tags=["Proposals"],
        dependencies=[Depends(get_current_user)],
    )
    workspace_context_dep = get_current_workspace_context or (lambda: None)

    def _empresa_activa(workspace_context: WorkspaceContext | None) -> UUID | None:
        return workspace_context.active_supplier_id if workspace_context else None

    def _exigir_permiso(workspace_context: WorkspaceContext | None) -> None:
        # Sin espacio de trabajo el usuario opera sobre su propia empresa.
        if (
            workspace_context is not None
            and PERMISO_ESCRITURA not in workspace_context.permissions
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para generar postulaciones en esta empresa",
            )

    @router.get(
        "/{tender_id}/proposal",
        response_model=ProposalDraftView,
        summary="Borrador de postulación de la empresa activa",
        responses={
            404: {"description": "No hay licitación, empresa o postulación iniciada"}
        },
    )
    async def get_proposal(
        tender_id: UUID,
        user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[GetProposalUseCase, Depends(get_proposal_use_case)],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
    ) -> ProposalDraftView:
        """Estado, exigencias y contenido. `is_expired` se calcula al leer: un
        borrador de una licitación cerrada se sigue mostrando."""
        try:
            return await use_case.execute(
                user_id=user.id,
                supplier_id=_empresa_activa(workspace_context),
                tender_id=tender_id,
            )
        except (
            TenderNotFound,
            SupplierNotFoundForUser,
            ProposalDraftNotFound,
        ) as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error

    @router.post(
        "/{tender_id}/proposal/feasibility",
        response_model=ProposalDraft,
        summary="Iniciar la postulación: análisis de factibilidad",
        responses={
            403: {"description": "Falta el permiso generate_proposal"},
            404: {"description": "La licitación o la empresa no existen"},
            409: {"description": "La licitación está cerrada para postulaciones"},
            502: {"description": "La IA no respondió o respondió algo inválido"},
        },
    )
    async def start_feasibility(
        tender_id: UUID,
        user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            StartFeasibilityUseCase, Depends(get_start_feasibility_use_case)
        ],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
    ) -> ProposalDraft:
        """Lee las bases, las cruza con el catálogo de la empresa y crea las
        preguntas que falten (CA6, etapa "Analizando bases y experiencia"). Si ya
        hay borrador lo devuelve tal cual, sin volver a llamar a la IA."""
        _exigir_permiso(workspace_context)
        try:
            return await use_case.execute(
                user_id=user.id,
                supplier_id=_empresa_activa(workspace_context),
                tender_id=tender_id,
            )
        except (TenderNotFound, SupplierNotFoundForUser) as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
        except TenderClosedForProposal as error:
            raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
        except ProposalAIServiceError as error:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "No fue posible analizar las bases en este momento. Intenta de nuevo.",
            ) from error

    return router
