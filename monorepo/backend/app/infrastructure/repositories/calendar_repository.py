from uuid import UUID

from sqlalchemy import delete
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.calendar_repository import (
    ICalendarConnectionRepository,
    ICalendarEventLinkRepository,
    ICalendarOAuthStateRepository,
)
from app.application.services.token_cipher import ITokenCipher
from app.domain.entities.calendar import (
    CalendarConnection,
    CalendarConnectionStatus,
    CalendarEventLink,
    CalendarOAuthState,
    CalendarProvider,
)
from app.infrastructure.repositories.calendar_model import (
    CalendarConnectionModel,
    CalendarEventLinkModel,
    CalendarOAuthStateModel,
)


class CalendarConnectionRepository(ICalendarConnectionRepository):
    """Cifra los tokens al guardar y los descifra al leer."""

    def __init__(self, session: AsyncSession, cipher: ITokenCipher):
        self.session = session
        self.cipher = cipher

    async def _model(self, user_id: UUID, provider: CalendarProvider) -> CalendarConnectionModel | None:
        result = await self.session.exec(
            select(CalendarConnectionModel).where(
                CalendarConnectionModel.user_id == user_id,
                CalendarConnectionModel.provider == provider.value,
            )
        )
        return result.first()

    async def get(self, user_id: UUID, provider: CalendarProvider) -> CalendarConnection | None:
        model = await self._model(user_id, provider)
        if model is None:
            return None
        return CalendarConnection(
            id=model.id,
            user_id=model.user_id,
            provider=CalendarProvider(model.provider),
            access_token=self.cipher.decrypt(model.access_token_encrypted),
            refresh_token=self.cipher.decrypt(model.refresh_token_encrypted),
            expires_at=model.expires_at,
            account_email=model.account_email,
            status=CalendarConnectionStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def save(self, connection: CalendarConnection) -> None:
        model = await self._model(connection.user_id, connection.provider)
        if model is None:
            model = CalendarConnectionModel(
                id=connection.id,
                user_id=connection.user_id,
                provider=connection.provider.value,
                access_token_encrypted="",
                refresh_token_encrypted="",
                expires_at=connection.expires_at,
                status=connection.status.value,
                created_at=connection.created_at,
                updated_at=connection.updated_at,
            )
        model.access_token_encrypted = self.cipher.encrypt(connection.access_token.get_secret_value())
        model.refresh_token_encrypted = self.cipher.encrypt(connection.refresh_token.get_secret_value())
        model.expires_at = connection.expires_at
        model.account_email = connection.account_email
        model.status = connection.status.value
        model.updated_at = connection.updated_at
        self.session.add(model)
        await self.session.commit()

    async def delete(self, user_id: UUID, provider: CalendarProvider) -> None:
        await self.session.exec(
            delete(CalendarConnectionModel).where(
                col(CalendarConnectionModel.user_id) == user_id,
                col(CalendarConnectionModel.provider) == provider.value,
            )
        )
        await self.session.commit()


class CalendarOAuthStateRepository(ICalendarOAuthStateRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, state: CalendarOAuthState) -> None:
        self.session.add(
            CalendarOAuthStateModel(
                state_hash=state.state_hash,
                user_id=state.user_id,
                provider=state.provider.value,
                tender_id=state.tender_id,
                milestone_ids=[str(m) for m in state.milestone_ids],
                default_time=state.default_time,
                expires_at=state.expires_at,
                created_at=state.created_at,
            )
        )
        await self.session.commit()

    async def consume(self, state_hash: str) -> CalendarOAuthState | None:
        # DELETE ... RETURNING: dos callbacks concurrentes con el mismo state no
        # pueden consumirlo ambos.
        tabla = CalendarOAuthStateModel.__table__  # type: ignore[attr-defined]
        result = await self.session.execute(
            delete(CalendarOAuthStateModel)
            .where(col(CalendarOAuthStateModel.state_hash) == state_hash)
            .returning(*tabla.c)
        )
        fila = result.mappings().first()
        await self.session.commit()
        if fila is None:
            return None
        return CalendarOAuthState(
            state_hash=fila["state_hash"],
            user_id=fila["user_id"],
            provider=CalendarProvider(fila["provider"]),
            tender_id=fila["tender_id"],
            milestone_ids=[UUID(m) for m in fila["milestone_ids"]],
            default_time=fila["default_time"],
            expires_at=fila["expires_at"],
            created_at=fila["created_at"],
        )


class CalendarEventLinkRepository(ICalendarEventLinkRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_entity(model: CalendarEventLinkModel) -> CalendarEventLink:
        return CalendarEventLink(
            id=model.id,
            user_id=model.user_id,
            milestone_id=model.milestone_id,
            provider=CalendarProvider(model.provider),
            external_event_id=model.external_event_id,
            synced_due_at=model.synced_due_at,
            last_synced_at=model.last_synced_at,
        )

    async def list_by_milestones(
        self, milestone_ids: list[UUID], provider: CalendarProvider
    ) -> list[CalendarEventLink]:
        if not milestone_ids:
            return []
        result = await self.session.exec(
            select(CalendarEventLinkModel).where(
                col(CalendarEventLinkModel.milestone_id).in_(milestone_ids),
                CalendarEventLinkModel.provider == provider.value,
            )
        )
        return [self._to_entity(m) for m in result.all()]

    async def save(self, link: CalendarEventLink) -> None:
        result = await self.session.exec(
            select(CalendarEventLinkModel).where(
                CalendarEventLinkModel.milestone_id == link.milestone_id,
                CalendarEventLinkModel.provider == link.provider.value,
            )
        )
        model = result.first()
        if model is None:
            model = CalendarEventLinkModel(
                id=link.id,
                user_id=link.user_id,
                milestone_id=link.milestone_id,
                provider=link.provider.value,
                external_event_id=link.external_event_id,
                synced_due_at=link.synced_due_at,
                last_synced_at=link.last_synced_at,
            )
        model.external_event_id = link.external_event_id
        model.synced_due_at = link.synced_due_at
        model.last_synced_at = link.last_synced_at
        self.session.add(model)
        await self.session.commit()
