from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.repositories.user_repository import IUserRepository
from app.application.services.identity_directory import IIdentityDirectory
from app.application.services.token_verifier import IAuthTokenVerifier
from app.application.use_cases.auth.resolve_authenticated_user import (
    ResolveAuthenticatedUserUseCase,
)
from app.domain.entities.user import User
from app.domain.errors.auth_errors import InvalidToken

# auto_error=False para poder devolver el 401 propio en vez del de FastAPI, con
# el `WWW-Authenticate` que corresponde. Declarar el esquema es además lo que
# hace aparecer el botón "Authorize" de Swagger, que es como se prueba la API a
# mano: se pega ahí el access token que el navegador ya tiene.
_bearer_scheme = HTTPBearer(auto_error=False)


def build_get_current_user(
    get_user_repo: Callable,
    get_token_verifier: Callable,
    get_identity_directory: Callable,
) -> Callable:
    """Construye la dependencia `get_current_user`.

    La sesión la emite Supabase Auth y viaja en `Authorization: Bearer`. Ya no
    se lee ninguna cookie: la de `@supabase/ssr` no es un JWT sino un JSON en
    base64 partido en varios trozos, y además lleva dentro el refresh token, así
    que reenviarla a este servicio sería mandarle una credencial de larga
    duración que no necesita.

    Verificado el token, se resuelve el perfil local —creándolo si es la primera
    vez— porque todo el esquema cuelga de `users.id`, no del `sub`.
    """

    async def get_current_user(
        user_repo: Annotated[IUserRepository, Depends(get_user_repo)],
        verifier: Annotated[IAuthTokenVerifier, Depends(get_token_verifier)],
        identity_directory: Annotated[
            IIdentityDirectory, Depends(get_identity_directory)
        ],
        credentials: Annotated[
            HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
        ] = None,
    ) -> User:
        unauthorized = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )

        if credentials is None or not credentials.credentials:
            raise unauthorized

        try:
            principal = await verifier.verify(credentials.credentials)
        except InvalidToken:
            raise unauthorized from None

        user = await ResolveAuthenticatedUserUseCase(
            user_repo=user_repo,
            identity_directory=identity_directory,
        ).execute(principal)

        # Desactivar una cuenta es una decisión nuestra, y el token de Supabase
        # sigue siendo válido hasta que expire: el corte tiene que estar acá.
        if not user.active:
            raise unauthorized

        return user

    return get_current_user
