from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.proveedor import Proveedor


class IProveedorRepository(ABC):

    @abstractmethod
    async def get_by_id(self, proveedor_id: UUID) -> Proveedor | None: ...

    @abstractmethod
    async def get_by_rut(self, rut: str) -> Proveedor | None: ...

    @abstractmethod
    async def save(self, proveedor: Proveedor) -> Proveedor: ...

    @abstractmethod
    async def update(self, proveedor: Proveedor) -> Proveedor: ...

    @abstractmethod
    async def delete(self, proveedor_id: UUID) -> None: ...