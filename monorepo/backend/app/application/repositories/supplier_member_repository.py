from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.supplier_member import (
    MemberStatus,
    SupplierMember,
    UserWorkspaceSummary,
)


class ISupplierMemberRepository(ABC):
    @abstractmethod
    async def get_by_id(self, member_id: UUID) -> SupplierMember | None: ...

    @abstractmethod
    async def get_by_user_and_supplier(
        self, user_id: UUID, supplier_id: UUID
    ) -> SupplierMember | None: ...

    @abstractmethod
    async def list_by_user_id(
        self, user_id: UUID, status: MemberStatus | None = None
    ) -> list[SupplierMember]: ...

    @abstractmethod
    async def list_by_supplier_id(
        self, supplier_id: UUID, status: MemberStatus | None = None
    ) -> list[SupplierMember]: ...

    @abstractmethod
    async def save(self, member: SupplierMember) -> SupplierMember: ...

    @abstractmethod
    async def add(self, member: SupplierMember) -> SupplierMember: ...

    @abstractmethod
    async def update(self, member: SupplierMember) -> SupplierMember: ...

    @abstractmethod
    async def delete(self, member_id: UUID) -> bool: ...

    @abstractmethod
    async def list_user_workspaces(
        self, user_id: UUID
    ) -> list[UserWorkspaceSummary]: ...
