from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.application.use_cases.deep_analysis.get_or_create_deep_analysis import (
    GetOrCreateDeepAnalysisUseCase,
)
from app.application.use_cases.matching.rank_tenders import RankTendersUseCase
from app.application.use_cases.saved_tenders.list_saved_tenders import (
    ListSavedTendersUseCase,
)
from app.application.use_cases.saved_tenders.save_tender import SaveTenderUseCase
from app.application.use_cases.saved_tenders.unsave_tender import UnsaveTenderUseCase
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.matching_result import MatchingResult
from app.domain.entities.saved_tender import SavedTender
from app.domain.entities.tender import Tender
from app.domain.entities.user import User
from app.domain.errors.deep_analysis_errors import (
    DeepAnalysisServiceError,
    InvalidPromptInstruction,
)
from app.domain.errors.matching_errors import ScoreMatchingNoEncontrado
from app.domain.errors.saved_tender_errors import SavedTenderNotFound
from app.domain.errors.supplier_errors import (
    SupplierNotFoundForUser,
    SupplierVectorNotFound,
)
from app.domain.errors.tender_errors import TenderNotFound


class DeepAnalysisRequest(BaseModel):
    prompt_instruction: str | None = Field(
        default=None,
        max_length=1000,
        description="Instrucciones adicionales para personalizar el análisis de compatibilidad (máx. 1000 caracteres).",
    )
    force_regenerate: bool = Field(
        default=False,
        description="Indica si se debe forzar una nueva generación de análisis ignorando el caché.",
    )
    only_if_exists: bool = Field(
        default=False,
        description="Si es True, no genera el análisis si no existe y en su lugar retorna un error 404.",
    )


def create_tender_router(
    get_rank_tenders_use_case: Callable,
    get_current_user: Callable,
    get_get_or_create_deep_analysis_use_case: Callable,
    get_list_saved_tenders_use_case: Callable,
    get_save_tender_use_case: Callable,
    get_unsave_tender_use_case: Callable,
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
        "/recommended",
        response_model=list[MatchingResult],
        responses={
            404: {
                "description": "No se encontró el perfil de proveedor o su vector asociado"
            },
        },
    )
    async def get_recommended_tenders(
        profile_id: UUID,
        use_case: Annotated[RankTendersUseCase, Depends(get_rank_tenders_use_case)],
        force_refresh: bool = False,
        # use_case: RankTendersUseCase = Depends(get_rank_tenders_use_case),
    ):
        """
        Retorna la lista de licitaciones recomendadas para el perfil de proveedor especificado.
        """
        try:
            return await use_case.execute(
                user_id=profile_id, force_refresh=force_refresh
            )
        except SupplierNotFoundForUser as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except SupplierVectorNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e

    # Declarada antes que las rutas con `{tender_id}` para que el segmento
    # estático "saved" nunca sea capturado como parámetro de path.
    @router.get("/saved", response_model=list[Tender])
    async def get_saved_tenders(
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            ListSavedTendersUseCase, Depends(get_list_saved_tenders_use_case)
        ],
    ):
        """
        Retorna únicamente las licitaciones que el usuario autenticado marcó como de interés.
        """
        return await use_case.execute(user_id=current_user.id)

    @router.post(
        "/{tender_id}/saved",
        response_model=SavedTender,
        status_code=status.HTTP_201_CREATED,
        responses={
            404: {"description": "La licitación no existe"},
        },
    )
    async def save_tender(
        tender_id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[SaveTenderUseCase, Depends(get_save_tender_use_case)],
    ):
        """
        Marca una licitación como de interés para el usuario autenticado.

        Es idempotente: repetir la llamada no duplica la licitación en la lista.
        """
        try:
            return await use_case.execute(user_id=current_user.id, tender_id=tender_id)
        except TenderNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e

    @router.delete(
        "/{tender_id}/saved",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={
            404: {"description": "La licitación no está en la lista de guardadas"},
        },
    )
    async def unsave_tender(
        tender_id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[UnsaveTenderUseCase, Depends(get_unsave_tender_use_case)],
    ):
        """
        Retira una licitación de la lista de guardadas del usuario autenticado.
        """
        try:
            await use_case.execute(user_id=current_user.id, tender_id=tender_id)
        except SavedTenderNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e

    @router.post(
        "/{tender_id}/analysis",
        response_model=DeepAnalysis,
        responses={
            400: {
                "description": "Instrucción de prompt inválida o detección de prompt injection"
            },
            404: {
                "description": "Licitación, proveedor o score de matching no encontrado"
            },
            422: {"description": "Error de validación de entradas"},
            502: {
                "description": "Error de comunicación con el servicio de IA (Gemini)"
            },
        },
    )
    async def analyze_tender_compatibility(
        tender_id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            GetOrCreateDeepAnalysisUseCase,
            Depends(get_get_or_create_deep_analysis_use_case),
        ],
        request_body: DeepAnalysisRequest | None = None,
        # current_user: User = Depends(get_current_user),
        # use_case: GetOrCreateDeepAnalysisUseCase = Depends(
        #     get_get_or_create_deep_analysis_use_case
        # ),
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
                    detail="El análisis de compatibilidad aún no ha sido generado.",
                )
            return analysis
        except SupplierNotFoundForUser as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except TenderNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except ScoreMatchingNoEncontrado as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except InvalidPromptInstruction as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        except DeepAnalysisServiceError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)
            ) from e

    return router
