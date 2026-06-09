from fastapi import Depends, FastAPI, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.user_repository import IUserRepository

from app.application.repositories.supplier_vector_repository import ISupplierVectorRepository
from app.config import settings
from app.infrastructure.auth.dependencies import build_get_current_user
from app.infrastructure.db import get_session
from app.infrastructure.repositories.qdrant_supplier_repository import (
    QdrantSupplierRepository,
)
from app.infrastructure.repositories.supplier_repository import SupplierRepository
from app.infrastructure.repositories.user_repository import UserRepository
from app.infrastructure.routers.router import create_router
from app.infrastructure.services.password_hasher import BcryptPasswordHasher
from app.infrastructure.services.token_service import JwtTokenService
from app.application.repositories.tender_repository import ITenderRepository
from app.infrastructure.repositories.tender_repository import TenderRepository
from app.application.repositories.tender_vector_repository import ITenderVectorRepository
from app.infrastructure.repositories.qdrant_tender_repository import QdrantTenderRepository
from app.application.services.reranker_service import IRerankerService
from app.infrastructure.services.bge_reranker_service import BgeRerankerService
from app.application.services.weighting_service import IWeightingService
from app.infrastructure.services.field_weighting_service import FieldWeightingService
from app.application.repositories.matching_result_repository import IMatchingResultRepository
from app.infrastructure.repositories.matching_result_repository import MatchingResultRepository
from app.application.use_cases.matching.rank_tenders import RankTendersUseCase



def get_supplier_repo(
    session: AsyncSession = Depends(get_session),
) -> ISupplierRepository:
    # Crea el repositorio concreto con la sesión de BD por petición
    return SupplierRepository(session)


def get_supplier_vector_repo(request: Request) -> ISupplierVectorRepository:
    # Reutiliza el cliente Qdrant inicializado en el lifespan
    return QdrantSupplierRepository(request.app.state.qdrant_client)

def get_tender_repo(
    session: AsyncSession = Depends(get_session),
) -> ITenderRepository:
    # Crea el repositorio concreto de licitaciones con la sesión de BD
    return TenderRepository(session)


def get_tender_vector_repo(request: Request) -> ITenderVectorRepository:
    # Reutiliza el cliente Qdrant asíncrono
    from app.routers.deps import get_qdrant_client
    return QdrantTenderRepository(
        client=get_qdrant_client(),
        vector_size=settings.embedding_vector_size,
    )
def get_reranker_service(request: Request) -> IRerankerService:
    return request.app.state.reranker_service


def get_weighting_service(request: Request) -> IWeightingService:
    return request.app.state.weighting_service



def get_matching_result_repo(
    session: AsyncSession = Depends(get_session),
) -> IMatchingResultRepository:
    return MatchingResultRepository(session)


def get_rank_tenders_use_case(
    session: AsyncSession = Depends(get_session),
    supplier_vector_repo: ISupplierVectorRepository = Depends(get_supplier_vector_repo),
    tender_vector_repo: ITenderVectorRepository = Depends(get_tender_vector_repo),
    reranker_service: IRerankerService = Depends(get_reranker_service),
    weighting_service: IWeightingService = Depends(get_weighting_service),
) -> RankTendersUseCase:
    return RankTendersUseCase(
        supplier_repo=SupplierRepository(session),
        supplier_vector_repo=supplier_vector_repo,
        tender_vector_repo=tender_vector_repo,
        tender_repo=TenderRepository(session),
        reranker_service=reranker_service,
        weighting_service=weighting_service,
        matching_result_repo=MatchingResultRepository(session),
        model_version=settings.embedding_model,
    )


def get_user_repo(session: AsyncSession = Depends(get_session)) -> IUserRepository:
    return UserRepository(session)



def bootstrap(app: FastAPI) -> None:
    # Servicios sin estado: se construyen una vez
    hasher = BcryptPasswordHasher()
    token_service = JwtTokenService(
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        expire_minutes=settings.access_token_expire_minutes,
    )

    # Inicialización de servicios de Reranking y Weighting con manejo robusto para ambientes de prueba
    try:
        app.state.reranker_service = BgeRerankerService()
    except Exception:
        # Fallback en caso de que falten dependencias u ONNX en ambiente local/tests
        class MockRerankerService(IRerankerService):
            async def rerank(self, query_text, candidates, limit):
                return [(c[0], 1.0) for c in candidates][:limit]
        app.state.reranker_service = MockRerankerService()

    app.state.weighting_service = FieldWeightingService(
        reranker_weight=0.5,
        region_weight=0.2,
        sector_weight=0.2,
        keyword_weight=0.1,
    )

    # Una sola instancia de la dependencia → FastAPI cachea el usuario por request
    get_current_user = build_get_current_user(
        get_user_repo=get_user_repo,
        token_service=token_service,
        cookie_name=settings.auth_cookie_name,
    )

    router = create_router(
        get_supplier_repo=get_supplier_repo,
        get_supplier_vector_repo=get_supplier_vector_repo,
        get_user_repo=get_user_repo,
        get_current_user=get_current_user,
        hasher=hasher,
        token_service=token_service,
        cookie_name=settings.auth_cookie_name,
        cookie_secure=settings.auth_cookie_secure,
        cookie_max_age=settings.access_token_expire_minutes * 60,
    )
    app.include_router(router)
