from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.supplier_invitation import (
    InvitationStatus,
    SupplierInvitation,
)


class ISupplierInvitationRepository(ABC):
    @abstractmethod
    async def get_by_id(self, invitation_id: UUID) -> SupplierInvitation | None: ...

    @abstractmethod
    async def get_by_token(self, token: str) -> SupplierInvitation | None: ...

    @abstractmethod
    async def list_by_supplier_id(
        self, supplier_id: UUID, status: InvitationStatus | None = None
    ) -> list[SupplierInvitation]: ...

    @abstractmethod
    async def list_by_email(
        self, email: str, status: InvitationStatus | None = None
    ) -> list[SupplierInvitation]: ...

    @abstractmethod
    async def save(self, invitation: SupplierInvitation) -> SupplierInvitation: ...

    @abstractmethod
    async def update(self, invitation: SupplierInvitation) -> SupplierInvitation: ...
