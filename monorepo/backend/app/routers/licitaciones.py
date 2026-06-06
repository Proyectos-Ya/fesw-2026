from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.services.text_builder import TextBuilder
from app.application.useCases.ingest_licitaciones import IngestLicitacionesUseCase
from app.core.config import settings
from app.domain.models.licitacion_schema import IngestRequest, IngestResult
from app.infrastructure.db import get_session
from app.infrastructure.repositories.licitacion_repository import LicitacionRepository
from app.routers.deps import (
    get_embedding_service,
    get_mercado_publico_client,
    get_vector_store,
)

router = APIRouter(prefix="/licitaciones", tags=["licitaciones"])


def get_ingest_use_case(
    session: AsyncSession = Depends(get_session),
) -> IngestLicitacionesUseCase:
    return IngestLicitacionesUseCase(
        mercado_publico=get_mercado_publico_client(),
        licitacion_repo=LicitacionRepository(session),
        embedding_service=get_embedding_service(),
        vector_store=get_vector_store(),
        text_builder=TextBuilder(),
        version_modelo=settings.embedding_model,
    )


@router.post("/ingest", response_model=IngestResult)
async def ingest_licitaciones(
    request: IngestRequest,
    use_case: IngestLicitacionesUseCase = Depends(get_ingest_use_case),
) -> IngestResult:
    return await use_case.execute(request)
