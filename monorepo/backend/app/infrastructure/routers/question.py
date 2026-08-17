from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.application.use_cases.questions.answer_question_use_case import (
    AnswerQuestionUseCase,
)
from app.application.use_cases.questions.smart_question_use_case import (
    SmartQuestionUseCase,
)

# from app.bootstrap import get_answer_question_use_case
from app.domain.entities.question import Question


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
        profileId: UUID = Query(
            ..., description="ID del Supplier para obtener su cuestionario"
        ),
        use_case: SmartQuestionUseCase = Depends(get_smart_question_use_case),
    ):
        """Retorna la cola de preguntas dinámicas para el Dashboard."""
        try:
            return await use_case.execute(provider_id=profileId)
        except Exception as e:
            print(f"[API Error] Error en GET /questions: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al procesar el árbol dinámico de preguntas.",
            ) from e

    class QuestionAnswerInput(BaseModel):
        supplier_id: UUID
        question_id: UUID
        target_profile_field: str
        answer: str

    @router.post("/answer", status_code=status.HTTP_200_OK)
    async def answer_question(
        payload: QuestionAnswerInput,
        use_case: AnswerQuestionUseCase = Depends(get_answer_question_use_case),
    ):
        try:
            await use_case.execute(
                supplier_id=payload.supplier_id,
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
