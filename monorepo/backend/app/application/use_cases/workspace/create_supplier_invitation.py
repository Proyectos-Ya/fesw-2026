from datetime import timedelta
import secrets
from uuid import UUID

from app.application.repositories.supplier_invitation_repository import (
    ISupplierInvitationRepository,
)
from app.application.repositories.supplier_member_repository import (
    ISupplierMemberRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.schemas.workspace_schema import CreateInvitationSchema
from app.domain.entities.supplier_invitation import (
    InvitationStatus,
    SupplierInvitation,
)
from app.domain.entities.supplier_member import MemberRole, MemberStatus
from app.domain.errors.membership_errors import (
    UnauthorizedWorkspaceAction,
    UserAlreadyMember,
)
from app.domain.errors.supplier_errors import SupplierNotFound
from app.shared.datetime_utils import utc_now_naive


class CreateSupplierInvitationUseCase:
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
        data: CreateInvitationSchema,
        inviter_user_id: UUID,
        expires_days: int = 7,
    ) -> SupplierInvitation:
        # 1. Verificar existencia de la empresa
        supplier = await self.supplier_repo.get_by_id(data.supplier_id)
        if not supplier:
            raise SupplierNotFound(str(data.supplier_id))

        # 2. Verificar que el usuario que invita sea administrador de la empresa
        inviter_membership = await self.member_repo.get_by_user_and_supplier(
            inviter_user_id, data.supplier_id
        )
        is_admin = False
        if inviter_membership and inviter_membership.is_admin():
            is_admin = True
        elif supplier.user_id == inviter_user_id:
            is_admin = True

        if not is_admin:
            raise UnauthorizedWorkspaceAction(
                "Solo los administradores pueden enviar invitaciones al espacio de trabajo."
            )

        # 3. Crear invitación con token seguro
        token = secrets.token_urlsafe(32)
        expires_at = utc_now_naive() + timedelta(days=expires_days)

        invitation = SupplierInvitation(
            supplier_id=data.supplier_id,
            email=data.email,
            role=data.role,
            invited_by_user_id=inviter_user_id,
            token=token,
            status=InvitationStatus.PENDING,
            expires_at=expires_at,
        )

        return await self.invitation_repo.save(invitation)
