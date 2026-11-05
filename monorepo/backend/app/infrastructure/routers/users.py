from collections.abc import Callable
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.application.repositories.user_repository import IUserRepository
from app.application.schemas.auth_schema import UserPublicSchema
from app.domain.entities.user import User


class UpdateOnboardingSchema(BaseModel):
    tour_name: Literal["home", "detail", "draft"]


def create_user_router(
    get_current_user: Callable,
    get_user_repo: Callable,
) -> APIRouter:
    router = APIRouter(tags=["Users"])

    @router.patch(
        "/api/v1/users/me/onboarding",
        response_model=UserPublicSchema,
        summary="Marcar tour contextual como completado",
    )
    @router.patch(
        "/users/me/onboarding",
        response_model=UserPublicSchema,
        summary="Marcar tour contextual como completado (alias /users)",
    )
    @router.patch(
        "/auth/me/onboarding",
        response_model=UserPublicSchema,
        summary="Marcar tour contextual como completado (alias /auth)",
    )
    async def mark_onboarding_completed(
        current_user: Annotated[User, Depends(get_current_user)],
        user_repo: Annotated[IUserRepository, Depends(get_user_repo)],
        payload: UpdateOnboardingSchema,
    ) -> User:
        update_data = {}
        if payload.tour_name == "home":
            update_data["tour_home_completed"] = True
        elif payload.tour_name == "detail":
            update_data["tour_detail_completed"] = True
        elif payload.tour_name == "draft":
            update_data["tour_draft_completed"] = True

        updated_user = current_user.model_copy(update=update_data)
        return await user_repo.save(updated_user)

    return router
