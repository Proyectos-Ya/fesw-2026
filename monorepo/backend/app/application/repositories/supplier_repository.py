from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.supplier import Supplier


class ISupplierRepository(ABC):
    @abstractmethod
    async def get_by_rut(self, rut: str) -> Supplier | None: ...

    @abstractmethod
    async def get_by_id(self, supplier_id: UUID) -> Supplier | None: ...

    @abstractmethod
    async def get_by_user_id(self, user_id: UUID) -> Supplier | None: ...

    @abstractmethod
    async def list_user_ids_with_profile(self) -> list[UUID]: ...

    @abstractmethod
    async def save(self, supplier: Supplier) -> Supplier: ...

    @abstractmethod
    async def update(self, supplier: Supplier) -> Supplier: ...
