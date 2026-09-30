"""Banco de capacidades de la empresa activa (HU-20).

Lo que la empresa declara que puede acreditar: respuestas a preguntas del banco
y los proyectos que las respaldan. Es la fuente que el borrador de postulación
cita en cada párrafo (CA5).

La empresa siempre es la activa del `WorkspaceContext`. Ver el catálogo lo puede
cualquier miembro; responder y agregar proyectos exige `generate_proposal`.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from app.application.schemas.capability_schema import (
    AddCapabilityEvidenceInput,
    AnswerCapabilityInput,
    PendingCapabilityQuestion,
)
from app.application.use_cases.capabilities.add_capability_evidence import (
    AddCapabilityEvidenceUseCase,
)
from app.application.use_cases.capabilities.answer_capability_question import (
    AnswerCapabilityQuestionUseCase,
)
from app.application.use_cases.capabilities.build_experience_catalog import (
    BuildExperienceCatalogUseCase,
)
from app.application.use_cases.capabilities.list_pending_questions import (
    ListPendingCapabilityQuestionsUseCase,
)
from app.domain.entities.capability import (
    CapabilityAnswer,
    CapabilityEvidence,
    ExperienceCatalog,
)
from app.domain.entities.supplier_member import WorkspaceContext
from app.domain.entities.user import User
from app.domain.errors.capability_errors import (
    CapabilityQuestionNotFound,
    EvidenceNeedsAffirmativeProjectAnswer,
    InvalidCapabilityAnswer,
)
from app.domain.errors.supplier_errors import SupplierNotFoundForUser

PERMISO_ESCRITURA = "generate_proposal"


def create_capability_router(
    get_current_user: Callable,
    get_build_catalog_use_case: Callable,
    get_answer_use_case: Callable,
    get_add_evidence_use_case: Callable,
    get_list_pending_use_case: Callable,
    get_current_workspace_context: Callable | None = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/capabilities",
        tags=["Capabilities"],
        dependencies=[Depends(get_current_user)],
    )
    workspace_context_dep = get_current_workspace_context or (lambda: None)

    def _empresa_activa(workspace_context: WorkspaceContext | None) -> UUID | None:
        return workspace_context.active_supplier_id if workspace_context else None

    def _exigir_permiso(workspace_context: WorkspaceContext | None) -> None:
        # Sin espacio de trabajo el usuario opera sobre su propia empresa, como
        # antes de las empresas múltiples; es el mismo criterio de `supplier.py`.
        if (
            workspace_context is not None
            and PERMISO_ESCRITURA not in workspace_context.permissions
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para modificar la experiencia de esta empresa",
            )

    @router.get(
        "/catalog",
        response_model=ExperienceCatalog,
        summary="Catálogo de experiencia de la empresa activa",
        responses={404: {"description": "El usuario no tiene empresa"}},
    )
    async def get_catalog(
        user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            BuildExperienceCatalogUseCase, Depends(get_build_catalog_use_case)
        ],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
    ) -> ExperienceCatalog:
        """Perfil, respuestas vigentes y proyectos, cada uno con un id estable
        (`perfil:…`, `capacidad:…`, `evidencia:…`) que el borrador usa para citar."""
        try:
            return await use_case.execute(
                user_id=user.id, supplier_id=_empresa_activa(workspace_context)
            )
        except SupplierNotFoundForUser as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error

    @router.get(
        "/questions/pending",
        response_model=list[PendingCapabilityQuestion],
        summary="Preguntas que la empresa activa tiene por responder",
        responses={404: {"description": "El usuario no tiene empresa"}},
    )
    async def list_pending(
        user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            ListPendingCapabilityQuestionsUseCase, Depends(get_list_pending_use_case)
        ],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
    ) -> list[PendingCapabilityQuestion]:
        """Sin responder ni omitir, o con la vigencia vencida. Cada una trae la
        licitación que la originó, si la hay."""
        try:
            return await use_case.execute(
                user_id=user.id, supplier_id=_empresa_activa(workspace_context)
            )
        except SupplierNotFoundForUser as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error

    @router.post(
        "/questions/{question_id}/answer",
        response_model=CapabilityAnswer,
        summary="Responder una pregunta del banco por la empresa activa",
        responses={
            403: {"description": "Falta el permiso generate_proposal"},
            404: {"description": "La pregunta o la empresa no existen"},
            422: {"description": "La respuesta no es una de las opciones"},
        },
    )
    async def answer_question(
        question_id: UUID,
        data: AnswerCapabilityInput,
        user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            AnswerCapabilityQuestionUseCase, Depends(get_answer_use_case)
        ],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
    ) -> CapabilityAnswer:
        """Crea o corrige la respuesta de la empresa. Queda registrado quién respondió."""
        _exigir_permiso(workspace_context)
        try:
            return await use_case.execute(
                user_id=user.id,
                supplier_id=_empresa_activa(workspace_context),
                question_id=question_id,
                answer=data.answer,
                valid_until=data.valid_until,
            )
        except (CapabilityQuestionNotFound, SupplierNotFoundForUser) as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
        except InvalidCapabilityAnswer as error:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)
            ) from error

    @router.post(
        "/questions/{question_id}/evidence",
        response_model=CapabilityEvidence,
        status_code=status.HTTP_201_CREATED,
        summary="Agregar un proyecto que respalda un Sí de experiencia",
        responses={
            403: {"description": "Falta el permiso generate_proposal"},
            404: {"description": "La pregunta o la empresa no existen"},
            409: {"description": "La empresa no respondió Sí a esa pregunta"},
            422: {"description": "Datos del proyecto inválidos"},
        },
    )
    async def add_evidence(
        question_id: UUID,
        data: AddCapabilityEvidenceInput,
        user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            AddCapabilityEvidenceUseCase, Depends(get_add_evidence_use_case)
        ],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(workspace_context_dep)
        ],
    ) -> CapabilityEvidence:
        """Solo sobre un "Sí" a una pregunta de experiencia en proyectos."""
        _exigir_permiso(workspace_context)
        try:
            return await use_case.execute(
                user_id=user.id,
                supplier_id=_empresa_activa(workspace_context),
                question_id=question_id,
                title=data.title,
                year=data.year,
                buyer=data.buyer,
                amount_clp=data.amount_clp,
                description=data.description,
            )
        except (CapabilityQuestionNotFound, SupplierNotFoundForUser) as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
        except EvidenceNeedsAffirmativeProjectAnswer as error:
            raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
        except ValidationError as error:
            # El año fuera de rango lo valida la entidad, no el esquema de entrada.
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Los datos del proyecto no son válidos.",
            ) from error

    return router
