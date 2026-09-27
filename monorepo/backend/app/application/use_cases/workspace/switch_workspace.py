from app.application.repositories.supplier_member_repository import (
    ISupplierMemberRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.schemas.workspace_schema import SwitchWorkspaceSchema
from app.domain.entities.supplier_member import (
    MemberRole,
    MemberStatus,
    WorkspaceContext,
)
from app.domain.entities.user import User
from app.domain.errors.membership_errors import (
    UnauthorizedWorkspaceAction,
)
from app.domain.errors.supplier_errors import SupplierNotFound


class SwitchWorkspaceUseCase:
    def __init__(
        self,
        member_repo: ISupplierMemberRepository,
        supplier_repo: ISupplierRepository,
    ):
        self.member_repo = member_repo
        self.supplier_repo = supplier_repo

    async def execute(
        self,
        current_user: User,
        data: SwitchWorkspaceSchema,
    ) -> WorkspaceContext:
        supplier = await self.supplier_repo.get_by_id(data.supplier_id)
        if not supplier:
            raise SupplierNotFound(str(data.supplier_id))

        member = await self.member_repo.get_by_user_and_supplier(
            current_user.id, data.supplier_id
        )

        all_perms = [
            "invite_members",
            "remove_members",
            "edit_company_profile",
            "manage_tenders",
            "view_matches",
            "save_tenders",
            "chat_assistant",
            "deep_analysis",
        ]

        if not member:
            # Compatibilidad legacy si es dueño
            if supplier.user_id == current_user.id:
                return WorkspaceContext(
                    user_id=current_user.id,
                    active_supplier_id=supplier.id,
                    active_supplier_name=supplier.trade_name or supplier.legal_name,
                    role=MemberRole.ADMIN,
                    permissions=all_perms,
                    is_admin=True,
                )
            raise UnauthorizedWorkspaceAction(
                "No tienes acceso a este espacio de trabajo."
            )

        if member.status != MemberStatus.ACTIVE:
            raise UnauthorizedWorkspaceAction(
                "Tu membresía en este espacio de trabajo está inactiva o suspendida."
            )

        active_perms = [p for p in all_perms if member.has_permission(p)]

        return WorkspaceContext(
            user_id=current_user.id,
            active_supplier_id=supplier.id,
            active_supplier_name=supplier.trade_name or supplier.legal_name,
            role=member.role,
            permissions=active_perms,
            is_admin=member.is_admin(),
        )
