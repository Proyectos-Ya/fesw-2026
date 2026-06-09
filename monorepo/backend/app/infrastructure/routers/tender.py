from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.use_cases.matching.rank_tenders import RankTendersUseCase
from app.domain.entities.matching_result import MatchingResult
from app.domain.errors.supplier_errors import SupplierNotFoundForUser, SupplierVectorNotFound


def create_tender_router(
    get_rank_tenders_use_case: Callable,
    get_current_user: Callable,
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

    return router
