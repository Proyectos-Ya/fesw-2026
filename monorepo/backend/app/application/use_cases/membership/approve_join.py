from datetime import datetime, timezone
from uuid import UUID

from app.application.repositories.membership_repository import IMembershipRepository
from app.application.use_cases.membership.admin_guard import ensure_active_admin
from app.domain.entities.membership import MembershipStatus, SupplierMembership
from app.domain.errors.membership_errors import MembershipNotFound


class ApproveJoinUseCase:
    """Un admin aprueba una solicitud pendiente: pasa a ACTIVE."""

    def __init__(self, membership_repo: IMembershipRepository):
        self.membership_repo = membership_repo

    async def execute(
        self, supplier_id: UUID, membership_id: UUID, actor_user_id: UUID
    ) -> SupplierMembership:
        # El actor debe ser admin activo del proveedor de la URL
        await ensure_active_admin(self.membership_repo, actor_user_id, supplier_id)

        target = await self.membership_repo.get_by_id(membership_id)
        # La solicitud debe existir y pertenecer a ese mismo proveedor
        if target is None or target.supplier_id != supplier_id:
            raise MembershipNotFound()

        target.status = MembershipStatus.ACTIVE
        target.joined_at = datetime.now(timezone.utc).replace(tzinfo=None)
        return await self.membership_repo.save(target)
