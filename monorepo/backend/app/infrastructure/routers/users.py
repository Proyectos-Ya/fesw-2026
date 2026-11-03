from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.application.repositories.user_repository import IUserRepository
from app.application.schemas.auth_schema import UserPublicSchema
from app.domain.entities.user import User


class UpdateOnboardingSchema(BaseModel):
    has_completed_onboarding: bool = True


def create_user_router(
    get_current_user: Callable,
    get_user_repo: Callable,
) -> APIRouter:
    router = APIRouter(tags=["Users"])

    @router.patch(
        "/api/v1/users/me/onboarding",
        response_model=UserPublicSchema,
        summary="Marcar onboarding como completado",
    )
    @router.patch(
        "/users/me/onboarding",
        response_model=UserPublicSchema,
        summary="Marcar onboarding como completado (alias /users)",
    )
    @router.patch(
        "/auth/me/onboarding",
        response_model=UserPublicSchema,
        summary="Marcar onboarding como completado (alias /auth)",
    )
    async def mark_onboarding_completed(
        current_user: Annotated[User, Depends(get_current_user)],
        user_repo: Annotated[IUserRepository, Depends(get_user_repo)],
        payload: UpdateOnboardingSchema | None = None,
    ) -> User:
        value = payload.has_completed_onboarding if payload is not None else True
        updated_user = current_user.model_copy(
            update={"has_completed_onboarding": value}
        )
        return await user_repo.save(updated_user)

    return router
