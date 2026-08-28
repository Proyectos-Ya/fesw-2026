from collections.abc import Callable
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.use_cases.matching.rank_tenders import RankTendersUseCase
from app.application.use_cases.deep_analysis.get_or_create_deep_analysis import GetOrCreateDeepAnalysisUseCase
from app.domain.entities.matching_result import MatchingResult
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.user import User
from app.domain.errors.supplier_errors import SupplierNotFoundForUser, SupplierVectorNotFound
from app.domain.errors.tender_errors import TenderNotFound
from app.domain.errors.matching_errors import ScoreMatchingNoEncontrado
from app.domain.errors.deep_analysis_errors import InvalidPromptInstruction, DeepAnalysisServiceError


class DeepAnalysisRequest(BaseModel):
    prompt_instruction: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Instrucciones adicionales para personalizar el análisis de compatibilidad (máx. 1000 caracteres)."
    )
    force_regenerate: bool = Field(
        default=False,
        description="Indica si se debe forzar una nueva generación de análisis ignorando el caché."
    )
    only_if_exists: bool = Field(
        default=False,
        description="Si es True, no genera el análisis si no existe y en su lugar retorna un error 404."
    )


def create_tender_router(
    get_rank_tenders_use_case: Callable,
    get_current_user: Callable,
    get_get_or_create_deep_analysis_use_case: Callable,
) -> APIRouter:
    """
    Fábrica del router de licitaciones (tenders).
    Todas las rutas requieren sesión de usuario activa.
    """
    router = APIRouter(
        prefix="/tenders",
        tags=["Tenders"],
        dependencies=[Depends(get_current_user)],
    )

    @router.get(
        "/recomended",
        response_model=list[MatchingResult],
        responses={
            404: {
                "description": "No se encontró el perfil de proveedor o su vector asociado"
            },
        },
    )
    async def get_recommended_tenders(
        profile_id: UUID,
        force_refresh: bool = False,
        use_case: RankTendersUseCase = Depends(get_rank_tenders_use_case),
    ):
        """
        Retorna la lista de licitaciones recomendadas para el perfil de proveedor especificado.
        """
        try:
            return await use_case.execute(user_id=profile_id, force_refresh=force_refresh)
        except SupplierNotFoundForUser as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except SupplierVectorNotFound as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    @router.post(
        "/{tender_id}/analysis",
        response_model=DeepAnalysis,
        responses={
            400: {"description": "Instrucción de prompt inválida o detección de prompt injection"},
            404: {"description": "Licitación, proveedor o score de matching no encontrado"},
            422: {"description": "Error de validación de entradas"},
            502: {"description": "Error de comunicación con el servicio de IA (Gemini)"},
        },
    )
    async def analyze_tender_compatibility(
        tender_id: UUID,
        request_body: Optional[DeepAnalysisRequest] = None,
        current_user: User = Depends(get_current_user),
        use_case: GetOrCreateDeepAnalysisUseCase = Depends(get_get_or_create_deep_analysis_use_case),
    ):
        """
        Genera u obtiene el análisis profundo de compatibilidad IA para una licitación.
        
        Permite personalizar las instrucciones de análisis (opcional, máx 1000 caracteres) y forzar la regeneración.
        """
        prompt_instruction = request_body.prompt_instruction if request_body else None
        force_regenerate = request_body.force_regenerate if request_body else False
        only_if_exists = request_body.only_if_exists if request_body else False

        try:
            analysis = await use_case.execute(
                tender_id=tender_id,
                user_id=current_user.id,
                force_regenerate=force_regenerate,
                prompt_instruction=prompt_instruction,
                only_if_exists=only_if_exists,
            )
            if analysis is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="El análisis de compatibilidad aún no ha sido generado."
                )
            return analysis
        except SupplierNotFoundForUser as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except TenderNotFound as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except ScoreMatchingNoEncontrado as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except InvalidPromptInstruction as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except DeepAnalysisServiceError as e:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    return router
