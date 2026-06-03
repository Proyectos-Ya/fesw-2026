from uuid import UUID

from app.application.repositories.membership_repository import IMembershipRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.domain.entities.membership import (
    MembershipRole,
    MembershipStatus,
    SupplierMembership,
)
from app.domain.errors.membership_errors import AlreadyHasSupplier
from app.domain.errors.supplier_errors import SupplierNotFound


class RequestJoinUseCase:
    """Crea una solicitud (pendiente) para unirse a una empresa por su RUT."""

    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        membership_repo: IMembershipRepository,
    ):
        self.supplier_repo = supplier_repo
        self.membership_repo = membership_repo

    async def execute(self, rut: str, user_id: UUID) -> SupplierMembership:
        # Por ahora un usuario solo puede estar/solicitar en una empresa
        if await self.membership_repo.get_by_user(user_id) is not None:
            raise AlreadyHasSupplier()

        supplier = await self.supplier_repo.get_by_rut(rut)
        if supplier is None:
            raise SupplierNotFound(rut)

        membership = SupplierMembership(
            user_id=user_id,
            supplier_id=supplier.id,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.PENDING,
        )
        return await self.membership_repo.save(membership)
