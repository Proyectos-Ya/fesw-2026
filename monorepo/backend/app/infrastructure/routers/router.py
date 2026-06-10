from typing import Callable
from fastapi import APIRouter

from app.application.services.password_hasher import IPasswordHasher
from app.application.services.token_service import ITokenService
from app.infrastructure.routers.auth import create_auth_router
from app.infrastructure.routers.health import create_health_router
from app.infrastructure.routers.supplier import create_supplier_router
from app.infrastructure.routers.tender import create_tender_router
from app.infrastructure.routers.question import create_question_router


def create_router(
    get_rank_tenders_use_case: Callable,
    get_smart_question_use_case: Callable,
    get_supplier_repo: Callable,
    get_supplier_vector_repo: Callable,
    get_embedding_service: Callable,
    get_user_repo: Callable,
    get_current_user: Callable,
    hasher: IPasswordHasher,
    token_service: ITokenService,
    cookie_name: str,
    cookie_secure: bool,
    cookie_max_age: int,
    get_get_or_create_deep_analysis_use_case: Callable,
) -> APIRouter:
    """Ensambla todos los sub-routers con sus dependencias inyectadas.

    Públicos: health (root + /health) y auth (register/login/logout).
    Protegidos (requieren sesión): suppliers.
    """
    root = APIRouter()

    # --- Rutas públicas ---
    root.include_router(create_health_router(), tags=["Health"])
    root.include_router(
        create_auth_router(
            get_user_repo=get_user_repo,
            hasher=hasher,
            token_service=token_service,
            get_current_user=get_current_user,
            cookie_name=cookie_name,
            cookie_secure=cookie_secure,
            cookie_max_age=cookie_max_age,
        )
    )

    # --- Rutas protegidas (la auth se aplica dentro de cada fábrica) ---
    root.include_router(
        create_supplier_router(
            get_supplier_repo=get_supplier_repo,
            get_supplier_vector_repo=get_supplier_vector_repo,
            get_embedding_service=get_embedding_service,
            get_current_user=get_current_user,
        )
    )
    root.include_router(
        create_tender_router(
            get_rank_tenders_use_case=get_rank_tenders_use_case,
            get_current_user=get_current_user,
            get_get_or_create_deep_analysis_use_case=get_get_or_create_deep_analysis_use_case,
        )
    )

    root.include_router(
        create_question_router(
            get_smart_question_use_case=get_smart_question_use_case,
            get_current_user=get_current_user,
        )
    )

    return root
