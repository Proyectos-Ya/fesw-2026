from uuid import UUID

from app.application.repositories.membership_repository import IMembershipRepository
from app.application.use_cases.membership.admin_guard import ensure_active_admin
from app.domain.errors.membership_errors import MembershipNotFound


class RejectJoinUseCase:
    """Un admin rechaza una solicitud pendiente: se elimina la fila."""

    def __init__(self, membership_repo: IMembershipRepository):
        self.membership_repo = membership_repo

    async def execute(
        self, supplier_id: UUID, membership_id: UUID, actor_user_id: UUID
    ) -> None:
        await ensure_active_admin(self.membership_repo, actor_user_id, supplier_id)

        target = await self.membership_repo.get_by_id(membership_id)
        if target is None or target.supplier_id != supplier_id:
            raise MembershipNotFound()

        await self.membership_repo.delete(membership_id)
