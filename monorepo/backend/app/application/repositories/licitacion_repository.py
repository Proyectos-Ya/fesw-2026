from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.licitacion import Licitacion


class ILicitacionRepository(ABC):

    @abstractmethod
    async def get_by_id(self, licitacion_id: UUID) -> Licitacion | None: ...

    @abstractmethod
    async def get_by_ids(self, ids: list[UUID]) -> list[Licitacion]: ...

    @abstractmethod
    async def get_by_codigo_externo(self, codigo_externo: str) -> Licitacion | None: ...

    @abstractmethod
    async def save(self, licitacion: Licitacion) -> Licitacion: ...
