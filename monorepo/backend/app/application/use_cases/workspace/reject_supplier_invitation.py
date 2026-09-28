from app.application.repositories.supplier_invitation_repository import (
    ISupplierInvitationRepository,
)
from app.domain.entities.supplier_invitation import (
    InvitationStatus,
    SupplierInvitation,
)
from app.domain.entities.user import User
from app.domain.errors.membership_errors import (
    InvitationAlreadyProcessed,
    InvitationCancelledOrInvalid,
    InvitationEmailMismatch,
    InvitationExpired,
    InvitationNotFound,
)


class RejectSupplierInvitationUseCase:
    def __init__(self, invitation_repo: ISupplierInvitationRepository):
        self.invitation_repo = invitation_repo

    async def execute(
        self,
        token: str,
        current_user: User,
    ) -> SupplierInvitation:
        invitation = await self.invitation_repo.get_by_token(token)
        if not invitation:
            raise InvitationNotFound("La invitación no existe o es inválida.")

        if invitation.status == InvitationStatus.CANCELLED:
            raise InvitationCancelledOrInvalid(
                "Esta invitación fue cancelada por el administrador."
            )

        if invitation.status in (
            InvitationStatus.ACCEPTED,
            InvitationStatus.REJECTED,
        ):
            raise InvitationAlreadyProcessed(
                "Esta invitación ya fue procesada previamente."
            )

        if invitation.is_expired():
            raise InvitationExpired("La invitación ha expirado.")

        if invitation.email.strip().lower() != current_user.email.strip().lower():
            raise InvitationEmailMismatch(
                f"Esta invitación fue enviada a {invitation.email}, pero tu sesión actual es {current_user.email}."
            )

        invitation.status = InvitationStatus.REJECTED
        return await self.invitation_repo.update(invitation)
