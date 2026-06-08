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


def get_supplier_repo(
    session: AsyncSession = Depends(get_session),
) -> ISupplierRepository:
    # Crea el repositorio concreto con la sesión de BD por petición
    return SupplierRepository(session)


def get_supplier_vector_repo(request: Request) -> ISupplierVectorRepository:
    # Reutiliza el cliente Qdrant inicializado en el lifespan
    return QdrantSupplierRepository(request.app.state.qdrant_client)


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
