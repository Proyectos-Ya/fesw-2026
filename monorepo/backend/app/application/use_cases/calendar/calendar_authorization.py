import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from uuid import UUID

from app.application.repositories.calendar_repository import (
    ICalendarConnectionRepository,
    ICalendarOAuthStateRepository,
)
from app.application.repositories.tender_milestone_repository import (
    ITenderMilestoneRepository,
)
from app.application.services.calendar_provider_client import (
    CalendarProviders,
    ICalendarProviderClient,
)
from app.domain.entities.calendar import (
    CalendarConnection,
    CalendarConnectionStatus,
    CalendarOAuthState,
    CalendarProvider,
)
from app.domain.errors.calendar_errors import (
    CalendarAuthExpired,
    CalendarNotConfigured,
    InvalidOAuthState,
)
from app.domain.errors.milestone_errors import MilestoneNotFound
from app.shared.datetime_utils import utc_now_naive

_VIGENCIA_STATE = timedelta(minutes=10)


def hash_state(state: str) -> str:
    return hashlib.sha256(state.encode()).hexdigest()


def provider_client(providers: CalendarProviders, provider: CalendarProvider) -> ICalendarProviderClient:
    client = providers.get(provider)
    if client is None:
        raise CalendarNotConfigured(provider)
    return client


@dataclass(frozen=True)
class CalendarAuthorizationResult:
    """Sincronización que el usuario pidió antes de ir a autorizar su calendario."""

    provider: CalendarProvider
    tender_id: UUID
    milestone_ids: list[UUID]
    default_time: time | None
    account_email: str | None


class StartCalendarAuthorizationUseCase:
    """Arma la redirección al proveedor, ligada a la sincronización pedida (criterio 2)."""

    def __init__(
        self,
        milestones: ITenderMilestoneRepository,
        states: ICalendarOAuthStateRepository,
        providers: CalendarProviders,
        now: Callable[[], datetime] = utc_now_naive,
    ):
        self.milestones = milestones
        self.states = states
        self.providers = providers
        self.now = now

    async def execute(
        self,
        user_id: UUID,
        provider: CalendarProvider,
        tender_id: UUID,
        milestone_ids: list[UUID],
        default_time: time | None,
    ) -> str:
        client = provider_client(self.providers, provider)
        pedidos = set(milestone_ids)
        encontrados = await self.milestones.list_by_ids(user_id, list(pedidos))
        if not pedidos or {m.id for m in encontrados if m.tender_id == tender_id} != pedidos:
            raise MilestoneNotFound()

        state = secrets.token_urlsafe(32)
        await self.states.save(
            CalendarOAuthState(
                state_hash=hash_state(state),
                user_id=user_id,
                provider=provider,
                tender_id=tender_id,
                milestone_ids=milestone_ids,
                default_time=default_time,
                expires_at=self.now() + _VIGENCIA_STATE,
            )
        )
        return client.authorization_url(state)


class CompleteCalendarAuthorizationUseCase:
    """Recibe el código del proveedor y guarda la conexión con los tokens (criterios 2 y 8)."""

    def __init__(
        self,
        states: ICalendarOAuthStateRepository,
        connections: ICalendarConnectionRepository,
        providers: CalendarProviders,
        now: Callable[[], datetime] = utc_now_naive,
    ):
        self.states = states
        self.connections = connections
        self.providers = providers
        self.now = now

    async def execute(
        self, user_id: UUID, provider: CalendarProvider, code: str, state: str
    ) -> CalendarAuthorizationResult:
        client = provider_client(self.providers, provider)
        pendiente = await self.states.consume(hash_state(state))
        if (
            pendiente is None
            or pendiente.provider is not provider
            or not pendiente.is_valid_for(user_id, self.now())
        ):
            raise InvalidOAuthState()

        tokens = await client.exchange_code(code)
        previa = await self.connections.get(user_id, provider)
        refresh_token = tokens.refresh_token or (
            previa.refresh_token.get_secret_value() if previa else None
        )
        if refresh_token is None:
            raise CalendarAuthExpired()

        ahora = self.now()
        conexion = CalendarConnection(
            user_id=user_id,
            provider=provider,
            access_token=tokens.access_token,
            refresh_token=refresh_token,
            expires_at=tokens.expires_at,
            account_email=tokens.account_email or (previa.account_email if previa else None),
            status=CalendarConnectionStatus.ACTIVE,
            created_at=ahora,
            updated_at=ahora,
        )
        if previa is not None:
            conexion = conexion.model_copy(update={"id": previa.id, "created_at": previa.created_at})
        await self.connections.save(conexion)
        return CalendarAuthorizationResult(
            provider=provider,
            tender_id=pendiente.tender_id,
            milestone_ids=pendiente.milestone_ids,
            default_time=pendiente.default_time,
            account_email=tokens.account_email,
        )
