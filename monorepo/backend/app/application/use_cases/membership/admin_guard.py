from uuid import UUID

from app.application.repositories.membership_repository import IMembershipRepository
from app.domain.entities.membership import (
    MembershipRole,
    MembershipStatus,
    SupplierMembership,
)
from app.domain.errors.membership_errors import NotAuthorized


async def ensure_active_admin(
    membership_repo: IMembershipRepository,
    actor_user_id: UUID,
    supplier_id: UUID,
) -> SupplierMembership:
    """Valida que el usuario sea admin activo del proveedor indicado.

    Lanza NotAuthorized si no es admin/activo o si administra otro proveedor.
    """
    membership = await membership_repo.get_by_user(actor_user_id)
    if (
        membership is None
        or membership.role != MembershipRole.ADMIN
        or membership.status != MembershipStatus.ACTIVE
        or membership.supplier_id != supplier_id
    ):
        raise NotAuthorized("Se requiere ser admin de este proveedor")
    return membership
