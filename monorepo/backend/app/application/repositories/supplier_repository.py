from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.supplier import Supplier


class ISupplierRepository(ABC):

    @abstractmethod
    async def get_by_rut(self, rut: str) -> Supplier | None:
        ...

    @abstractmethod
    async def get_by_id(self, supplier_id: UUID) -> Supplier | None:
        ...

    @abstractmethod
    async def save(self, supplier: Supplier) -> Supplier:
        ...
