import secrets
from datetime import timedelta
from uuid import UUID

from app.application.repositories.supplier_invitation_repository import (
    ISupplierInvitationRepository,
)
from app.application.repositories.supplier_member_repository import (
    ISupplierMemberRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.user_repository import IUserRepository
from app.application.schemas.workspace_schema import CreateInvitationSchema
from app.domain.entities.supplier_invitation import (
    InvitationStatus,
    SupplierInvitation,
)
from app.domain.entities.supplier_member import MemberStatus
from app.domain.errors.membership_errors import (
    InvitationAlreadyPending,
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
        user_repo: IUserRepository | None = None,
    ):
        self.invitation_repo = invitation_repo
        self.member_repo = member_repo
        self.supplier_repo = supplier_repo
        self.user_repo = user_repo

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

        normalized_email = data.email.strip().lower()

        # 3. Validar si el correo ya pertenece a un miembro activo (CA3)
        if self.user_repo is not None:
            existing_user = await self.user_repo.get_by_email(normalized_email)
            if existing_user is not None:
                if supplier.user_id == existing_user.id:
                    raise UserAlreadyMember(
                        "El usuario con este correo ya es miembro activo de la empresa."
                    )
                existing_member = await self.member_repo.get_by_user_and_supplier(
                    existing_user.id, data.supplier_id
                )
                if (
                    existing_member is not None
                    and existing_member.status == MemberStatus.ACTIVE
                ):
                    raise UserAlreadyMember(
                        "El usuario con este correo ya es miembro activo de la empresa."
                    )

        # 4. Validar si ya existe una invitación pendiente vigente para el mismo correo (CA3)
        pending_invitations = await self.invitation_repo.list_by_supplier_id(
            data.supplier_id, status=InvitationStatus.PENDING
        )
        for existing_inv in pending_invitations:
            if existing_inv.email.strip().lower() == normalized_email:
                if existing_inv.is_pending():
                    raise InvitationAlreadyPending(
                        f"Ya existe una invitación pendiente para {normalized_email} en esta empresa."
                    )
                existing_inv.status = InvitationStatus.EXPIRED
                await self.invitation_repo.update(existing_inv)

        # 5. Crear invitación con token seguro
        token = secrets.token_urlsafe(32)
        expires_at = utc_now_naive() + timedelta(days=expires_days)

        invitation = SupplierInvitation(
            supplier_id=data.supplier_id,
            email=normalized_email,
            role=data.role,
            invited_by_user_id=inviter_user_id,
            token=token,
            status=InvitationStatus.PENDING,
            expires_at=expires_at,
        )

        return await self.invitation_repo.save(invitation)

