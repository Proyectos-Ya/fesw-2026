from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.application.use_cases.questions.answer_question_use_case import (
    AnswerQuestionUseCase,
)
from app.application.use_cases.questions.smart_question_use_case import (
    SmartQuestionUseCase,
)

# from app.bootstrap import get_answer_question_use_case
from app.domain.entities.question import Question
from app.domain.entities.user import User


def create_question_router(
    get_smart_question_use_case: Callable,
    get_current_user: Callable,
) -> APIRouter:

    router = APIRouter(
        prefix="/questions",
        tags=["Smart Questions"],
        dependencies=[Depends(get_current_user)],  # Obliga a estar logeado
    )

    from app.bootstrap import get_answer_question_use_case

    @router.get(
        "",
        response_model=list[Question],
        responses={
            500: {"description": "Error interno del servidor"},
        },
    )
    async def get_smart_questions(
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[SmartQuestionUseCase, Depends(get_smart_question_use_case)],
    ):
        """Cola de preguntas dinámicas para la empresa del usuario autenticado.

        `profileId` se elimina por la misma razón que en `/tenders/recommended`:
        la identidad no debe venir del cliente. Aquí la filtración era menor —el
        banco de preguntas es estático y solo se elegía entre tres categorías—
        pero la comprobación faltaba igual, y el arreglo es el mismo.
        """
        try:
            return await use_case.execute(user_id=current_user.id)
        except Exception as e:
            print(f"[API Error] Error en GET /questions: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al procesar el árbol dinámico de preguntas.",
            ) from e

    class QuestionAnswerInput(BaseModel):
        # Sin `supplier_id`: la empresa se deduce de la sesión. Un cliente que
        # siga mandándolo no rompe —pydantic ignora los campos de más— pero el
        # valor no se usa.
        question_id: UUID
        target_profile_field: str
        answer: str

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
                field_name=payload.target_profile_field,
                answer=payload.answer,
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
