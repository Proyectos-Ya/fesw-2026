from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.services.text_builder import TextBuilder
from app.application.useCases.match_licitaciones import MatchLicitacionesUseCase
from app.application.useCases.obtener_score_matching import ObtenerScoreMatchingUseCase
from app.core.config import settings
from app.domain.entities.resultado_matching import ResultadoMatching
from app.domain.errors.matching_errors import ScoreMatchingNoEncontrado
from app.domain.errors.proveedor_errors import ProveedorNoEncontrado
from app.domain.models.matching_schema import (
    MatchRequest,
    MatchResult,
    ObtenerScoreRequest,
)
from app.infrastructure.db import get_session
from app.infrastructure.repositories.proveedor_repository import ProveedorRepository
from app.infrastructure.repositories.resultado_matching_repository import (
    ResultadoMatchingRepository,
)
from app.routers.deps import get_embedding_service, get_vector_store

router = APIRouter(prefix="/matching", tags=["matching"])


def get_match_use_case(
    session: AsyncSession = Depends(get_session),
) -> MatchLicitacionesUseCase:
    return MatchLicitacionesUseCase(
        proveedor_repo=ProveedorRepository(session),
        embedding_service=get_embedding_service(),
        vector_store=get_vector_store(),
        resultado_matching_repo=ResultadoMatchingRepository(session),
        text_builder=TextBuilder(),
        version_modelo=settings.embedding_model,
    )


def get_obtener_score_use_case(
    session: AsyncSession = Depends(get_session),
) -> ObtenerScoreMatchingUseCase:
    return ObtenerScoreMatchingUseCase(
        resultado_matching_repo=ResultadoMatchingRepository(session),
    )


@router.post("/", response_model=MatchResult)
async def match_licitaciones(
    request: MatchRequest,
    use_case: MatchLicitacionesUseCase = Depends(get_match_use_case),
) -> MatchResult:
    try:
        return await use_case.execute(request)
    except ProveedorNoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{proveedor_id}/{licitacion_id}", response_model=ResultadoMatching)
async def obtener_score(
    proveedor_id: UUID,
    licitacion_id: UUID,
    use_case: ObtenerScoreMatchingUseCase = Depends(get_obtener_score_use_case),
) -> ResultadoMatching:
    try:
        return await use_case.execute(
            ObtenerScoreRequest(
                proveedor_id=proveedor_id,
                licitacion_id=licitacion_id,
            )
        )
    except ScoreMatchingNoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
