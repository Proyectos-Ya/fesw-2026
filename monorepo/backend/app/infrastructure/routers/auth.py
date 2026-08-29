from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.application.repositories.user_repository import IUserRepository
from app.application.schemas.auth_schema import (
    LoginSchema,
    RegisterSchema,
    TokenSchema,
    UserPublicSchema,
)
from app.application.services.password_hasher import IPasswordHasher
from app.application.services.token_service import ITokenService
from app.application.use_cases.auth.login_user import LoginUserUseCase
from app.application.use_cases.auth.register_user import RegisterUserUseCase
from app.config import settings
from app.domain.entities.user import User
from app.domain.errors.auth_errors import (
    InactiveUser,
    InvalidCredentials,
    UserAlreadyExists,
)


def create_auth_router(
    get_user_repo: Callable,
    hasher: IPasswordHasher,
    token_service: ITokenService,
    get_current_user: Callable,
    cookie_name: str,
    cookie_secure: bool,
    cookie_max_age: int,
) -> APIRouter:
    """Fábrica del router de autenticación.

    register/login/logout son públicos; /me requiere sesión.
    """
    router = APIRouter(prefix="/auth", tags=["Auth"])

    @router.post(
        "/register",
        response_model=UserPublicSchema,
        status_code=status.HTTP_201_CREATED,
        responses={409: {"description": "El correo ya está registrado"}},
    )
    async def register(
        data: RegisterSchema,
        # repo: IUserRepository = Depends(get_user_repo),
        repo: Annotated[IUserRepository, Depends(get_user_repo)],
    ):
        try:
            return await RegisterUserUseCase(repo, hasher).execute(data)
        except UserAlreadyExists as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(e)
            ) from e

    @router.post(
        "/login",
        response_model=TokenSchema,
        responses={401: {"description": "Credenciales inválidas o cuenta inactiva"}},
    )
    async def login(
        data: LoginSchema,
        response: Response,
        # repo: IUserRepository = Depends(get_user_repo),
        repo: Annotated[IUserRepository, Depends(get_user_repo)],
    ):
        try:
            token, _ = await LoginUserUseCase(repo, hasher, token_service).execute(data)
        except (InvalidCredentials, InactiveUser) as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)
            ) from e

        # Cookie httpOnly para el frontend; el token también va en el body para Swagger
        response.set_cookie(
            key=cookie_name,
            value=token,
            httponly=True,
            secure=cookie_secure,
            samesite=settings.auth_cookie_samesite,
            max_age=cookie_max_age,
        )
        return TokenSchema(access_token=token)

    @router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
    async def logout(response: Response):
        # Borra la cookie de sesión
        response.delete_cookie(key=cookie_name)
        return None

    @router.get("/me", response_model=UserPublicSchema)
    # async def me(current_user: User = Depends(get_current_user)):
    async def me(current_user: Annotated[User, Depends(get_current_user)]):
        return current_user

    return router
