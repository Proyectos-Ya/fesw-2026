from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.repositories.membership_repository import IMembershipRepository
from app.application.schemas.membership_schema import MembershipPublicSchema
from app.application.use_cases.membership.get_user_membership import (
    GetUserMembershipUseCase,
)
from app.domain.entities.user import User
from app.domain.errors.membership_errors import MembershipNotFound, NotAuthorized


def create_users_router(
    get_membership_repo: Callable,
    get_current_user: Callable,
) -> APIRouter:
    """Rutas centradas en el usuario. Requieren sesión."""
    router = APIRouter(
        prefix="/users",
        tags=["Users"],
        dependencies=[Depends(get_current_user)],
    )

    @router.get(
        "/{user_id}/membership",
        response_model=MembershipPublicSchema,
        responses={
            403: {"description": "No autorizado a ver esta membresía"},
            404: {"description": "El usuario no pertenece a ningún proveedor"},
        },
    )
    async def get_user_membership(
        user_id: UUID,
        current_user: User = Depends(get_current_user),
        membership_repo: IMembershipRepository = Depends(get_membership_repo),
    ):
        # El propio usuario, o un admin del proveedor de ese usuario
        try:
            return await GetUserMembershipUseCase(membership_repo).execute(
                user_id, current_user.id
            )
        except MembershipNotFound as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except NotAuthorized as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    return router
