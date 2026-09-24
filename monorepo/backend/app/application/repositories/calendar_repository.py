from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.calendar import (
    CalendarConnection,
    CalendarEventLink,
    CalendarOAuthState,
    CalendarProvider,
)


class ICalendarConnectionRepository(ABC):
    @abstractmethod
    async def get(self, user_id: UUID, provider: CalendarProvider) -> CalendarConnection | None: ...

    @abstractmethod
    async def save(self, connection: CalendarConnection) -> None:
        """Crea o reemplaza la conexión del usuario con ese proveedor."""

    @abstractmethod
    async def delete(self, user_id: UUID, provider: CalendarProvider) -> None: ...


class ICalendarOAuthStateRepository(ABC):
    @abstractmethod
    async def save(self, state: CalendarOAuthState) -> None: ...

    @abstractmethod
    async def consume(self, state_hash: str) -> CalendarOAuthState | None:
        """Devuelve el estado y lo borra en la misma operación: es de un solo uso."""


class ICalendarEventLinkRepository(ABC):
    @abstractmethod
    async def list_by_milestones(
        self, milestone_ids: list[UUID], provider: CalendarProvider
    ) -> list[CalendarEventLink]: ...

    @abstractmethod
    async def save(self, link: CalendarEventLink) -> None:
        """Crea o actualiza el enlace del hito con ese proveedor."""
