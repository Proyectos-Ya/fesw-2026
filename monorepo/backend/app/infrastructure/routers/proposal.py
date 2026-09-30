"""Postulación a una Compra Ágil: borrador de la empresa activa (HU-20).

B2 expone la factibilidad y la lectura del borrador; B3, responder, decidir ante
una discrepancia y reanudar; B4, redactar. Regenerar y exportar llegan después.
"""

import logging
from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.schemas.proposal_schema import (
    AnswerProposalQuestionInput,
    DecideDiscrepancyInput,
    ProposalDraftView,
)
from app.application.services.proposal_ai_service import ProposalAIServiceError
from app.application.use_cases.proposals.answer_proposal_question import (
    AnswerProposalQuestionUseCase,
)
from app.application.use_cases.proposals.decide_discrepancy import (
    DecideDiscrepancyUseCase,
)
from app.application.use_cases.proposals.generate_proposal import (
    GenerateProposalUseCase,
)
from app.application.use_cases.proposals.get_proposal import GetProposalUseCase
from app.application.use_cases.proposals.resume_proposal import ResumeProposalUseCase
from app.application.use_cases.proposals.start_feasibility import (
    StartFeasibilityUseCase,
)
from app.domain.entities.proposal import ProposalDraft
from app.domain.entities.supplier_member import WorkspaceContext
from app.domain.entities.user import User
from app.domain.errors.capability_errors import (
    CapabilityQuestionNotFound,
    InvalidCapabilityAnswer,
)
from app.domain.errors.proposal_errors import (
    InvalidProposalTransition,
    ProposalDraftNotFound,
    QuestionNotInProposal,
)
from app.domain.errors.supplier_errors import SupplierNotFoundForUser
from app.domain.errors.tender_errors import TenderClosedForProposal, TenderNotFound

logger = logging.getLogger(__name__)

PERMISO_ESCRITURA = "generate_proposal"


def create_proposal_router(
    get_current_user: Callable,
    get_start_feasibility_use_case: Callable,
    get_proposal_use_case: Callable,
    get_answer_proposal_question_use_case: Callable,
    get_decide_discrepancy_use_case: Callable,
    get_resume_proposal_use_case: Callable,
    get_generate_proposal_use_case: Callable,
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
            # Al usuario no se le muestra el detalle técnico, pero tiene que
            # quedar en el log: sin él un 502 no se puede diagnosticar.
            logger.warning(
                "Falló la factibilidad de la licitación %s: %s", tender_id, error
            )
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "No fue posible analizar las bases en este momento. Intenta de nuevo.",
            ) from error

    _NO_ENCONTRADO = (
        TenderNotFound,
        SupplierNotFoundForUser,
        ProposalDraftNotFound,
        QuestionNotInProposal,
        CapabilityQuestionNotFound,
    )
    _CONFLICTO = (TenderClosedForProposal, InvalidProposalTransition)
    _ERRORES_DE_ESCRITURA = {
        403: {"description": "Falta el permiso generate_proposal"},
        404: {"description": "No hay licitación, empresa, postulación o pregunta"},
        409: {
            "description": "La licitación cerró o la acción no corresponde al estado"
        },
    }

    def _traducir(error: Exception) -> HTTPException:
        if isinstance(error, _NO_ENCONTRADO):
            return HTTPException(status.HTTP_404_NOT_FOUND, str(error))
        if isinstance(error, _CONFLICTO):
            return HTTPException(status.HTTP_409_CONFLICT, str(error))
        return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error))

    @router.post(
        "/{tender_id}/proposal/questions/{question_id}/answer",
        response_model=ProposalDraft,
        summary="Responder una pregunta de la postulación",
        responses={
            **_ERRORES_DE_ESCRITURA,
            422: {"description": "La respuesta no es una de las opciones"},
        },
    )
    async def answer_question(
        tender_id: UUID,
        question_id: UUID,
        data: AnswerProposalQuestionInput,
        user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            AnswerProposalQuestionUseCase,
            Depends(get_answer_proposal_question_use_case),
        ],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
    ) -> ProposalDraft:
        """Guarda la respuesta en el banco de la empresa y mueve el borrador. Un
        "No" a una exigencia excluyente lo pausa (CA7). En pausa solo se acepta la
        pregunta de la exigencia pausada, para actualizarla."""
        _exigir_permiso(workspace_context)
        try:
            return await use_case.execute(
                user_id=user.id,
                supplier_id=_empresa_activa(workspace_context),
                tender_id=tender_id,
                question_id=question_id,
                answer=data.answer,
            )
        except (*_NO_ENCONTRADO, *_CONFLICTO, InvalidCapabilityAnswer) as error:
            raise _traducir(error) from error

    @router.post(
        "/{tender_id}/proposal/discrepancy",
        response_model=ProposalDraft,
        summary="Continuar con advertencia o detener ante un No excluyente",
        responses=_ERRORES_DE_ESCRITURA,
    )
    async def decide_discrepancy(
        tender_id: UUID,
        data: DecideDiscrepancyInput,
        user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            DecideDiscrepancyUseCase, Depends(get_decide_discrepancy_use_case)
        ],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
    ) -> ProposalDraft:
        """`continue` agrega la advertencia y sigue (CA8); `stop` detiene el
        borrador hasta que se reanude (CA9). Si la pausa ya no es la exigencia
        indicada, responde 409."""
        _exigir_permiso(workspace_context)
        try:
            return await use_case.execute(
                user_id=user.id,
                supplier_id=_empresa_activa(workspace_context),
                tender_id=tender_id,
                requirement_id=data.requirement_id,
                action=data.action,
            )
        except (*_NO_ENCONTRADO, *_CONFLICTO) as error:
            raise _traducir(error) from error

    @router.post(
        "/{tender_id}/proposal/resume",
        response_model=ProposalDraft,
        summary="Reanudar una postulación detenida",
        responses=_ERRORES_DE_ESCRITURA,
    )
    async def resume_proposal(
        tender_id: UUID,
        user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            ResumeProposalUseCase, Depends(get_resume_proposal_use_case)
        ],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
    ) -> ProposalDraft:
        """Vuelve a factibilidad para que la empresa pueda corregir la respuesta
        que detuvo la postulación (CA9)."""
        _exigir_permiso(workspace_context)
        try:
            return await use_case.execute(
                user_id=user.id,
                supplier_id=_empresa_activa(workspace_context),
                tender_id=tender_id,
            )
        except (*_NO_ENCONTRADO, *_CONFLICTO) as error:
            raise _traducir(error) from error

    @router.post(
        "/{tender_id}/proposal/generate",
        response_model=ProposalDraft,
        summary="Redactar el borrador de la oferta",
        responses={
            **_ERRORES_DE_ESCRITURA,
            409: {
                "description": "Quedan preguntas, hay una pausa, está detenido "
                "o la licitación cerró"
            },
            502: {"description": "La IA no respondió o respondió algo inválido"},
        },
    )
    async def generate_proposal(
        tender_id: UUID,
        user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            GenerateProposalUseCase, Depends(get_generate_proposal_use_case)
        ],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
    ) -> ProposalDraft:
        """Nombre, descripción, documentos necesarios y, si las bases lo exigen,
        documento técnico (CA1), con los vacíos marcados (CA2) y la fuente de
        cada párrafo (CA5). Etapa "Redactando…" del CA6. Deja el borrador en
        `READY`."""
        _exigir_permiso(workspace_context)
        try:
            return await use_case.execute(
                user_id=user.id,
                supplier_id=_empresa_activa(workspace_context),
                tender_id=tender_id,
            )
        except (*_NO_ENCONTRADO, *_CONFLICTO) as error:
            raise _traducir(error) from error
        except ProposalAIServiceError as error:
            logger.warning(
                "Falló la redacción de la licitación %s: %s", tender_id, error
            )
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "No fue posible redactar el borrador en este momento. Intenta de nuevo.",
            ) from error

    return router
