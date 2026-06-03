from uuid import UUID

from app.application.repositories.membership_repository import IMembershipRepository
from app.application.use_cases.membership.admin_guard import ensure_active_admin
from app.domain.entities.membership import MembershipStatus, SupplierMembership


class ListMembershipsUseCase:
    """Lista las membresías de un proveedor, opcionalmente filtradas por estado."""

    def __init__(self, membership_repo: IMembershipRepository):
        self.membership_repo = membership_repo

    async def execute(
        self,
        supplier_id: UUID,
        actor_user_id: UUID,
        status: MembershipStatus | None = None,
    ) -> list[SupplierMembership]:
        await ensure_active_admin(self.membership_repo, actor_user_id, supplier_id)
        return await self.membership_repo.list_by_supplier(supplier_id, status)
