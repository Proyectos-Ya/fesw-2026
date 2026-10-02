from uuid import UUID

from app.application.repositories.supplier_member_repository import (
    ISupplierMemberRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.domain.entities.supplier_member import MemberStatus, SupplierMember
from app.domain.errors.membership_errors import (
    CannotRevokeOwnMembership,
    MembershipNotFound,
    UnauthorizedWorkspaceAction,
)
from app.domain.errors.supplier_errors import SupplierNotFound
from app.shared.datetime_utils import utc_now_naive


class RevokeSupplierMemberUseCase:
    """Caso de uso para que un administrador revoque el acceso de un miembro (HU-13)."""

    def __init__(
        self,
        member_repo: ISupplierMemberRepository,
        supplier_repo: ISupplierRepository,
    ):
        self.member_repo = member_repo
        self.supplier_repo = supplier_repo

    async def execute(
        self,
        supplier_id: UUID,
        member_id: UUID,
        actor_user_id: UUID,
    ) -> SupplierMember:
        supplier = await self.supplier_repo.get_by_id(supplier_id)
        if not supplier:
            raise SupplierNotFound(str(supplier_id))

        caller_member = await self.member_repo.get_by_user_and_supplier(
            actor_user_id, supplier_id
        )
        is_admin = (caller_member is not None and caller_member.is_admin()) or (
            supplier.user_id == actor_user_id
            and (caller_member is None or caller_member.status == MemberStatus.ACTIVE)
        )
        if not is_admin:
            raise UnauthorizedWorkspaceAction(
                "Solo los administradores pueden revocar el acceso de miembros del equipo."
            )

        # Caso propietario legacy cuyo ID de fila sintético en la tabla de equipo es supplier.id
        if member_id == supplier.id and supplier.user_id == actor_user_id:
            raise CannotRevokeOwnMembership(
                "No puedes revocar tu propio acceso como administrador."
            )

        target_member = await self.member_repo.get_by_id(member_id)
        if not target_member or target_member.supplier_id != supplier_id:
            raise MembershipNotFound(
                "No se encontró el miembro especificado en esta empresa."
            )

        if target_member.user_id == actor_user_id:
            raise CannotRevokeOwnMembership(
                "No puedes revocar tu propio acceso como administrador."
            )

        now = utc_now_naive()
        target_member.status = MemberStatus.INACTIVE
        target_member.updated_at = now
        return await self.member_repo.update(target_member)
