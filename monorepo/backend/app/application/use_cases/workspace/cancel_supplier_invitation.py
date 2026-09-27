from uuid import UUID

from app.application.repositories.supplier_invitation_repository import (
    ISupplierInvitationRepository,
)
from app.application.repositories.supplier_member_repository import (
    ISupplierMemberRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.domain.entities.supplier_invitation import (
    InvitationStatus,
    SupplierInvitation,
)
from app.domain.errors.membership_errors import (
    InvitationAlreadyProcessed,
    InvitationNotFound,
    UnauthorizedWorkspaceAction,
)
from app.domain.errors.supplier_errors import SupplierNotFound


class CancelSupplierInvitationUseCase:
    def __init__(
        self,
        invitation_repo: ISupplierInvitationRepository,
        member_repo: ISupplierMemberRepository,
        supplier_repo: ISupplierRepository,
    ):
        self.invitation_repo = invitation_repo
        self.member_repo = member_repo
        self.supplier_repo = supplier_repo

    async def execute(
        self,
        invitation_id: UUID,
        actor_user_id: UUID,
    ) -> SupplierInvitation:
        invitation = await self.invitation_repo.get_by_id(invitation_id)
        if not invitation:
            raise InvitationNotFound("La invitación no existe.")

        supplier = await self.supplier_repo.get_by_id(invitation.supplier_id)
        if not supplier:
            raise SupplierNotFound(str(invitation.supplier_id))

        actor_membership = await self.member_repo.get_by_user_and_supplier(
            actor_user_id, invitation.supplier_id
        )
        is_admin = False
        if actor_membership and actor_membership.is_admin():
            is_admin = True
        elif supplier.user_id == actor_user_id:
            is_admin = True

        if not is_admin:
            raise UnauthorizedWorkspaceAction(
                "Solo los administradores pueden cancelar invitaciones."
            )

        if invitation.status != InvitationStatus.PENDING:
            raise InvitationAlreadyProcessed(
                "Solo se pueden cancelar invitaciones que estén pendientes."
            )

        invitation.status = InvitationStatus.CANCELLED
        return await self.invitation_repo.update(invitation)
