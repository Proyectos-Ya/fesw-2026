from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.application.use_cases.questions.answer_question_use_case import (
    AnswerQuestionUseCase,
)
from app.application.use_cases.questions.generate_tender_smart_questions_use_case import (
    GenerateTenderSmartQuestionsUseCase,
)
from app.application.use_cases.questions.smart_question_use_case import (
    SmartQuestionUseCase,
)
from app.domain.entities.question import Question
from app.domain.entities.supplier_member import WorkspaceContext
from app.domain.entities.user import User


def create_question_router(
    get_smart_question_use_case: Callable,
    get_answer_question_use_case: Callable,
    get_current_user: Callable,
    get_generate_tender_smart_questions_use_case: Callable | None = None,
    get_current_workspace_context: Callable | None = None,
) -> APIRouter:

    router = APIRouter(
        prefix="/questions",
        tags=["Smart Questions"],
        dependencies=[Depends(get_current_user)],  # Obliga a estar logeado
    )

    generate_dep = (
        get_generate_tender_smart_questions_use_case
        if get_generate_tender_smart_questions_use_case is not None
        else lambda: None
    )
    workspace_dep = (
        get_current_workspace_context
        if get_current_workspace_context is not None
        else lambda: None
    )

    def _empresa_activa(workspace_context: WorkspaceContext | None) -> UUID | None:
        return workspace_context.active_supplier_id if workspace_context else None

    @router.get(
        "",
        response_model=list[Question],
        responses={
            400: {"description": "Petición inválida o recurso no encontrado"},
            500: {"description": "Error interno del servidor"},
        },
    )
    async def get_smart_questions(
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[SmartQuestionUseCase, Depends(get_smart_question_use_case)],
        generate_use_case: Annotated[
            GenerateTenderSmartQuestionsUseCase | None,
            Depends(generate_dep),
        ] = None,
        workspace_context: Annotated[
            WorkspaceContext | None,
            Depends(workspace_dep),
        ] = None,
        tender_id: UUID | None = None,
    ):
        """Cola de preguntas dinámicas para la empresa del usuario autenticado.

        Si `tender_id` está presente, genera o recupera preguntas estratégicas asociadas
        a esa licitación mediante IA y análisis de bases. Si se omite, retorna la cola general.
        """
        try:
            active_supplier = _empresa_activa(workspace_context)
            kwargs = {"supplier_id": active_supplier} if active_supplier is not None else {}
            if tender_id is not None and generate_use_case is not None:
                return await generate_use_case.execute(
                    user_id=current_user.id,
                    tender_id=tender_id,
                    **kwargs,
                )
            return await use_case.execute(
                user_id=current_user.id,
                **kwargs,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        except Exception as e:
            print(f"[API Error] Error en GET /questions: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al procesar el árbol dinámico de preguntas.",
            ) from e

    class QuestionAnswerInput(BaseModel):
        question_id: UUID
        answer: str
        target_profile_field: str | None = None
        supplier_id: UUID | None = None

    @router.post("/answer", status_code=status.HTTP_200_OK)
    async def answer_question(
        payload: QuestionAnswerInput,
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            AnswerQuestionUseCase, Depends(get_answer_question_use_case)
        ],
    ):
        try:
            await use_case.execute(
                user_id=current_user.id,
                question_id=payload.question_id,
                answer=payload.answer,
                field_name=payload.target_profile_field,
            )
            return {
                "status": "success",
                "detail": "Respuesta procesada y perfil actualizado en keywords con éxito.",
            }
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        except Exception as e:
            print(
                f"💥 [CRITICAL ERROR] Falló el POST /questions/answer. Motivo: {repr(e)}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error interno al procesar la respuesta del cuestionario inteligente.",
            ) from e

    return router
