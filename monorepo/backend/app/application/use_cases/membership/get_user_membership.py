from uuid import UUID

from app.application.repositories.membership_repository import IMembershipRepository
from app.application.use_cases.membership.admin_guard import ensure_active_admin
from app.domain.entities.membership import SupplierMembership
from app.domain.errors.membership_errors import MembershipNotFound


class GetUserMembershipUseCase:
    """Devuelve la membresía de un usuario.

    Puede consultarla el propio usuario o un admin del proveedor al que ese
    usuario pertenece (ensure_active_admin valida lo segundo).
    """

    def __init__(self, membership_repo: IMembershipRepository):
        self.membership_repo = membership_repo

    async def execute(
        self, target_user_id: UUID, actor_user_id: UUID
    ) -> SupplierMembership:
        target = await self.membership_repo.get_by_user(target_user_id)

        if actor_user_id == target_user_id:
            # El propio usuario consulta su estado
            if target is None:
                raise MembershipNotFound()
            return target

        # Un tercero solo puede verla si es admin del proveedor de ese usuario
        if target is None:
            raise MembershipNotFound()
        await ensure_active_admin(
            self.membership_repo, actor_user_id, target.supplier_id
        )
        return target
