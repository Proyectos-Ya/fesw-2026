from collections.abc import Callable
from datetime import time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from app.application.use_cases.calendar.calendar_authorization import (
    CompleteCalendarAuthorizationUseCase,
    StartCalendarAuthorizationUseCase,
)
from app.application.use_cases.calendar.calendar_connections import (
    DisconnectCalendarUseCase,
    GetCalendarConnectionsUseCase,
)
from app.domain.entities.calendar import CalendarProvider
from app.domain.entities.user import User
from app.domain.errors.calendar_errors import (
    CalendarAuthExpired,
    CalendarError,
    CalendarNotConfigured,
    CalendarPermissionMissing,
    CalendarProviderUnavailable,
    InvalidOAuthState,
)
from app.domain.errors.milestone_errors import MilestoneNotFound

HoraMinuto = Annotated[time, PlainSerializer(lambda t: t.strftime("%H:%M"), return_type=str)]

_ESTADOS: dict[type[Exception], int] = {
    MilestoneNotFound: 404,
    InvalidOAuthState: 400,
    CalendarPermissionMissing: 403,
    CalendarAuthExpired: 409,
    CalendarProviderUnavailable: 502,
    CalendarNotConfigured: 503,
}


class CalendarConnectionResponse(BaseModel):
    provider: CalendarProvider
    connected: bool
    account_email: str | None
    needs_reconnect: bool


class AuthorizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tender_id: UUID
    milestone_ids: list[UUID] = Field(min_length=1, max_length=50)
    default_time: time | None = None


class AuthorizeResponse(BaseModel):
    authorization_url: str


class CallbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=2048)
    state: str = Field(min_length=1, max_length=256)


class CallbackResponse(BaseModel):
    provider: CalendarProvider
    tender_id: UUID
    milestone_ids: list[UUID]
    default_time: HoraMinuto | None
    account_email: str | None


def _http(error: Exception) -> HTTPException:
    estado = next((s for tipo, s in _ESTADOS.items() if isinstance(error, tipo)), 500)
    return HTTPException(estado, str(error))


def create_calendar_router(
    get_current_user: Callable,
    get_calendar_connections_use_case: Callable,
    get_start_calendar_authorization_use_case: Callable,
    get_complete_calendar_authorization_use_case: Callable,
    get_disconnect_calendar_use_case: Callable,
) -> APIRouter:
    router = APIRouter(prefix="/calendar", tags=["Calendar"])

    @router.get("/connections", response_model=list[CalendarConnectionResponse])
    async def list_connections(
        user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[GetCalendarConnectionsUseCase, Depends(get_calendar_connections_use_case)],
    ):
        return [
            CalendarConnectionResponse(
                provider=c.provider,
                connected=c.connected,
                account_email=c.account_email,
                needs_reconnect=c.needs_reconnect,
            )
            for c in await use_case.execute(user.id)
        ]

    @router.post("/{provider}/authorize", response_model=AuthorizeResponse)
    async def authorize(
        provider: CalendarProvider,
        body: AuthorizeRequest,
        user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            StartCalendarAuthorizationUseCase, Depends(get_start_calendar_authorization_use_case)
        ],
    ):
        try:
            url = await use_case.execute(
                user.id, provider, body.tender_id, body.milestone_ids, body.default_time
            )
        except (CalendarError, MilestoneNotFound) as error:
            raise _http(error) from error
        return AuthorizeResponse(authorization_url=url)

    @router.post("/{provider}/callback", response_model=CallbackResponse)
    async def callback(
        provider: CalendarProvider,
        body: CallbackRequest,
        user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            CompleteCalendarAuthorizationUseCase,
            Depends(get_complete_calendar_authorization_use_case),
        ],
    ):
        try:
            resultado = await use_case.execute(user.id, provider, body.code, body.state)
        except CalendarError as error:
            raise _http(error) from error
        return CallbackResponse(
            provider=resultado.provider,
            tender_id=resultado.tender_id,
            milestone_ids=resultado.milestone_ids,
            default_time=resultado.default_time,
            account_email=resultado.account_email,
        )

    @router.delete("/connections/{provider}", status_code=204)
    async def disconnect(
        provider: CalendarProvider,
        user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[DisconnectCalendarUseCase, Depends(get_disconnect_calendar_use_case)],
    ):
        try:
            await use_case.execute(user.id, provider)
        except CalendarError as error:
            raise _http(error) from error
        return Response(status_code=204)

    return router
