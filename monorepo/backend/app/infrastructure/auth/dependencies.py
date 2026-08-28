from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.repositories.user_repository import IUserRepository
from app.application.services.token_service import ITokenService
from app.domain.entities.user import User
from app.domain.errors.auth_errors import InvalidToken

# auto_error=False: si no hay header Authorization no falla aquí; intentamos la cookie.
# Declarar el esquema hace que el botón "Authorize" de Swagger funcione.
_bearer_scheme = HTTPBearer(auto_error=False)


def build_get_current_user(
    get_user_repo: Callable,
    token_service: ITokenService,
    cookie_name: str,
) -> Callable:
    """Construye la dependencia get_current_user.

    Acepta el token desde el header 'Authorization: Bearer' (Swagger) o desde
    la cookie httpOnly (frontend). Devuelve la entidad User autenticada.
    """

    async def get_current_user(
        request: Request,
        user_repo: Annotated[IUserRepository, Depends(get_user_repo)],
        credentials: Annotated[
            HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
        ] = None,
        # credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
        # user_repo: IUserRepository = Depends(get_user_repo),
    ) -> User:
        # 1) Header Authorization tiene prioridad; 2) si no, la cookie
        token = (
            credentials.credentials if credentials else request.cookies.get(cookie_name)
        )

        unauthorized = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )
        if not token:
            raise unauthorized

        try:
            user_id = token_service.decode_token(token)
        except InvalidToken:
            raise unauthorized from None

        user = await user_repo.get_by_id(user_id)
        if user is None or not user.active:
            raise unauthorized

        return user

    return get_current_user
