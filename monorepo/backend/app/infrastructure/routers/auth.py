from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.schemas.auth_schema import UserPublicSchema
from app.domain.entities.user import User


def create_auth_router(get_current_user: Callable) -> APIRouter:
    """Fábrica del router de autenticación.

    Ya no hay register/login/logout: las emite Supabase Auth desde el navegador,
    y el backend solo valida el token que le llega. Lo que queda es `/me`, que
    no es un endpoint de conveniencia:

    - Es donde se aprovisiona el perfil local la primera vez que alguien entra
      (lo hace `get_current_user`).
    - Es la única forma que tiene el frontend de conocer el `users.id` nuestro,
      distinto del `sub` de Supabase, y al que apuntan todas las claves foráneas
      del esquema.
    """
    router = APIRouter(prefix="/auth", tags=["Auth"])

    @router.get(
        "/me",
        response_model=UserPublicSchema,
        summary="Perfil local de quien hace la petición",
        responses={401: {"description": "Sin sesión o token inválido"}},
    )
    async def me(current_user: Annotated[User, Depends(get_current_user)]):
        return current_user

    return router
