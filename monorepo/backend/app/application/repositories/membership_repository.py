from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.membership import MembershipStatus, SupplierMembership


class IMembershipRepository(ABC):

    @abstractmethod
    async def save(self, membership: SupplierMembership) -> SupplierMembership:
        ...

    @abstractmethod
    async def get_by_id(self, membership_id: UUID) -> SupplierMembership | None:
        ...

    @abstractmethod
    async def get_by_user(self, user_id: UUID) -> SupplierMembership | None:
        """Devuelve la (única) membresía del usuario, o None.

        Por ahora un usuario pertenece a una sola empresa, así que devuelve
        a lo sumo una fila (pendiente o activa).
        """
        ...

    @abstractmethod
    async def list_by_supplier(
        self, supplier_id: UUID, status: MembershipStatus | None = None
    ) -> list[SupplierMembership]:
        ...

    @abstractmethod
    async def delete(self, membership_id: UUID) -> None:
        ...
