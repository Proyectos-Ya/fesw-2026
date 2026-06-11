from collections.abc import Callable
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel

from app.application.use_cases.questions.smart_question_use_case import SmartQuestionUseCase
from app.domain.entities.question import Question
from app.application.use_cases.questions.answer_question_use_case import AnswerQuestionUseCase

def create_question_router(
    get_smart_question_use_case: Callable,
    get_current_user: Callable,
) -> APIRouter:
    
    router = APIRouter(
        prefix="/questions",
        tags=["Smart Questions"],
        dependencies=[Depends(get_current_user)],  # Obliga a estar logeado
    )

    @router.get(
        "",
        response_model=list[Question],
        responses={
            500: {"description": "Error interno del servidor"},
        },
    )
    async def get_smart_questions(
        profileId: UUID = Query(..., description="ID del Supplier para obtener su cuestionario"),
        use_case: SmartQuestionUseCase = Depends(get_smart_question_use_case),
    ):
        """Retorna la cola de preguntas dinámicas para el Dashboard."""
        try:
            return await use_case.execute(provider_id=profileId)
        except Exception as e:
            print(f"[API Error] Error en GET /questions: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al procesar el árbol dinámico de preguntas."
            )

    class QuestionAnswerInput(BaseModel):
        supplier_id: UUID
        question_id: UUID
        target_profile_field: str
        answer: str

    @router.post("/answer", status_code=status.HTTP_200_OK)
    async def answer_question(
        payload: QuestionAnswerInput,
    ):  
        from app.bootstrap import get_answer_question_use_case

        try:
            use_case: AnswerQuestionUseCase = get_answer_question_use_case()

            await use_case.execute(
                supplier_id=payload.supplier_id,
                field_name=payload.target_profile_field,
                answer=payload.answer
            )
            return {
                "status": "success", 
                "detail": "Respuesta procesada y perfil actualizado en keywords con éxito."
            }
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail="Error interno al procesar la respuesta del cuestionario inteligente."
            )

    return router