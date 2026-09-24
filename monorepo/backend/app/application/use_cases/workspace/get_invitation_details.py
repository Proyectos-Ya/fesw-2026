from app.application.repositories.supplier_invitation_repository import (
    ISupplierInvitationRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.schemas.workspace_schema import InvitationDetailsSchema
from app.domain.errors.membership_errors import (
    InvitationExpired,
    InvitationNotFound,
)
from app.domain.errors.supplier_errors import SupplierNotFound


class GetInvitationDetailsUseCase:
    def __init__(
        self,
        invitation_repo: ISupplierInvitationRepository,
        supplier_repo: ISupplierRepository,
    ):
        self.invitation_repo = invitation_repo
        self.supplier_repo = supplier_repo

    async def execute(self, token: str) -> InvitationDetailsSchema:
        invitation = await self.invitation_repo.get_by_token(token)
        if not invitation:
            raise InvitationNotFound("La invitación no existe o es inválida.")

        if invitation.is_expired():
            raise InvitationExpired("La invitación ha expirado.")

        supplier = await self.supplier_repo.get_by_id(invitation.supplier_id)
        if not supplier:
            raise SupplierNotFound(str(invitation.supplier_id))

        supplier_name = supplier.trade_name or supplier.legal_name

        return InvitationDetailsSchema(
            id=invitation.id,
            supplier_id=invitation.supplier_id,
            supplier_name=supplier_name,
            email=invitation.email,
            role=invitation.role,
            status=invitation.status,
            expires_at=invitation.expires_at,
            created_at=invitation.created_at,
        )
