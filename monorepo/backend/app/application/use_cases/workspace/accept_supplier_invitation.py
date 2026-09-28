from app.application.repositories.supplier_invitation_repository import (
    ISupplierInvitationRepository,
)
from app.application.repositories.supplier_member_repository import (
    ISupplierMemberRepository,
)
from app.domain.entities.supplier_invitation import InvitationStatus
from app.domain.entities.supplier_member import (
    MemberRole,
    MemberStatus,
    SupplierMember,
)
from app.domain.entities.user import User
from app.domain.errors.membership_errors import (
    InvitationAlreadyProcessed,
    InvitationEmailMismatch,
    InvitationExpired,
    InvitationNotFound,
)
from app.shared.datetime_utils import utc_now_naive


class AcceptSupplierInvitationUseCase:
    def __init__(
        self,
        invitation_repo: ISupplierInvitationRepository,
        member_repo: ISupplierMemberRepository,
    ):
        self.invitation_repo = invitation_repo
        self.member_repo = member_repo

    async def execute(
        self,
        token: str,
        current_user: User,
    ) -> SupplierMember:
        invitation = await self.invitation_repo.get_by_token(token)
        if not invitation:
            raise InvitationNotFound("La invitación no existe o es inválida.")

        if invitation.status == InvitationStatus.ACCEPTED:
            raise InvitationAlreadyProcessed("Esta invitación ya fue aceptada previamente.")

        if invitation.is_expired():
            raise InvitationExpired("La invitación ha expirado.")

        # Verificar que el email coincida con la cuenta activa
        if invitation.email.strip().lower() != current_user.email.strip().lower():
            raise InvitationEmailMismatch(
                f"Esta invitación fue enviada a {invitation.email}, pero tu sesión actual es {current_user.email}."
            )

        # Verificar si ya existe membresía
        existing_membership = await self.member_repo.get_by_user_and_supplier(
            current_user.id, invitation.supplier_id
        )

        now = utc_now_naive()
        if existing_membership:
            # Si existía inactiva, la reactivamos con el nuevo rol
            existing_membership.role = invitation.role
            existing_membership.status = MemberStatus.ACTIVE
            existing_membership.updated_at = now
            member = await self.member_repo.update(existing_membership)
        else:
            new_membership = SupplierMember(
                user_id=current_user.id,
                supplier_id=invitation.supplier_id,
                role=invitation.role,
                status=MemberStatus.ACTIVE,
                created_at=now,
                updated_at=now,
            )
            member = await self.member_repo.save(new_membership)

        # Actualizar estado de la invitación
        invitation.status = InvitationStatus.ACCEPTED
        invitation.accepted_at = now
        await self.invitation_repo.update(invitation)

        return member
