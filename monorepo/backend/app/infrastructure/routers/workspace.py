from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.application.repositories.supplier_invitation_repository import (
    ISupplierInvitationRepository,
)
from app.application.repositories.supplier_member_repository import (
    ISupplierMemberRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.schemas.workspace_schema import (
    AcceptInvitationSchema,
    CreateInvitationSchema,
    InvitationDetailsSchema,
    WorkspaceMemberSummarySchema,
)
from app.application.use_cases.workspace.accept_supplier_invitation import (
    AcceptSupplierInvitationUseCase,
)
from app.application.use_cases.workspace.create_supplier_invitation import (
    CreateSupplierInvitationUseCase,
)
from app.application.use_cases.workspace.get_invitation_details import (
    GetInvitationDetailsUseCase,
)
from app.domain.entities.supplier_invitation import (
    InvitationStatus,
    SupplierInvitation,
)
from app.domain.entities.supplier_member import UserWorkspaceSummary
from app.domain.entities.user import User
from app.domain.errors.membership_errors import (
    InvitationAlreadyProcessed,
    InvitationEmailMismatch,
    InvitationExpired,
    InvitationNotFound,
    UnauthorizedWorkspaceAction,
    UserAlreadyMember,
)
from app.domain.errors.supplier_errors import SupplierNotFound


def create_workspace_router(
    get_current_user: Callable,
    get_supplier_member_repo: Callable,
    get_supplier_invitation_repo: Callable,
    get_supplier_repo: Callable,
) -> APIRouter:
    router = APIRouter(
        prefix="/workspaces",
        tags=["Workspaces & Invitations"],
    )

    # 1. Listar los espacios de trabajo del usuario autenticado (CA-2)
    @router.get(
        "",
        response_model=list[UserWorkspaceSummary],
        summary="Lista las empresas/espacios de trabajo del usuario autenticado",
    )
    async def list_my_workspaces(
        current_user: Annotated[User, Depends(get_current_user)],
        member_repo: Annotated[
            ISupplierMemberRepository, Depends(get_supplier_member_repo)
        ],
        supplier_repo: Annotated[ISupplierRepository, Depends(get_supplier_repo)],
    ):
        workspaces = await member_repo.list_user_workspaces(current_user.id)
        if not workspaces:
            # Fallback legacy si existía en supplier.user_id
            legacy_supplier = await supplier_repo.get_by_user_id(current_user.id)
            if legacy_supplier:
                from app.domain.entities.supplier_member import (
                    MemberRole,
                    MemberStatus,
                )

                workspaces.append(
                    UserWorkspaceSummary(
                        supplier_id=legacy_supplier.id,
                        legal_name=legacy_supplier.legal_name,
                        trade_name=legacy_supplier.trade_name,
                        rut=legacy_supplier.rut,
                        role=MemberRole.ADMIN,
                        status=MemberStatus.ACTIVE,
                        is_active_context=True,
                    )
                )
        return workspaces

    # 2. Crear una invitación para unirse a un espacio de trabajo
    @router.post(
        "/invitations",
        response_model=SupplierInvitation,
        status_code=status.HTTP_201_CREATED,
        summary="Enviar invitación a un usuario para unirse al espacio de trabajo",
    )
    async def create_invitation(
        data: CreateInvitationSchema,
        current_user: Annotated[User, Depends(get_current_user)],
        invitation_repo: Annotated[
            ISupplierInvitationRepository, Depends(get_supplier_invitation_repo)
        ],
        member_repo: Annotated[
            ISupplierMemberRepository, Depends(get_supplier_member_repo)
        ],
        supplier_repo: Annotated[ISupplierRepository, Depends(get_supplier_repo)],
    ):
        try:
            return await CreateSupplierInvitationUseCase(
                invitation_repo=invitation_repo,
                member_repo=member_repo,
                supplier_repo=supplier_repo,
            ).execute(data, inviter_user_id=current_user.id)
        except SupplierNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except UnauthorizedWorkspaceAction as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
            ) from e

    # 3. Verificar token de invitación (público o autenticado)
    @router.get(
        "/invitations/verify",
        response_model=InvitationDetailsSchema,
        summary="Obtener detalles de una invitación mediante su token",
    )
    async def verify_invitation(
        token: Annotated[str, Query(min_length=1)],
        invitation_repo: Annotated[
            ISupplierInvitationRepository, Depends(get_supplier_invitation_repo)
        ],
        supplier_repo: Annotated[ISupplierRepository, Depends(get_supplier_repo)],
    ):
        try:
            return await GetInvitationDetailsUseCase(
                invitation_repo=invitation_repo,
                supplier_repo=supplier_repo,
            ).execute(token)
        except InvitationNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except InvitationExpired as e:
            raise HTTPException(
                status_code=status.HTTP_410_GONE, detail=str(e)
            ) from e
        except SupplierNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e

    # 4. Aceptar invitación con la cuenta autenticada (CA-1)
    @router.post(
        "/invitations/accept",
        response_model=WorkspaceMemberSummarySchema,
        summary="Aceptar una invitación y vincular la empresa a la cuenta actual",
    )
    async def accept_invitation(
        data: AcceptInvitationSchema,
        current_user: Annotated[User, Depends(get_current_user)],
        invitation_repo: Annotated[
            ISupplierInvitationRepository, Depends(get_supplier_invitation_repo)
        ],
        member_repo: Annotated[
            ISupplierMemberRepository, Depends(get_supplier_member_repo)
        ],
    ):
        try:
            member = await AcceptSupplierInvitationUseCase(
                invitation_repo=invitation_repo,
                member_repo=member_repo,
            ).execute(token=data.token, current_user=current_user)

            return WorkspaceMemberSummarySchema(
                id=member.id,
                user_id=member.user_id,
                supplier_id=member.supplier_id,
                role=member.role,
                status=member.status,
                created_at=member.created_at,
            )
        except InvitationNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except (InvitationExpired, InvitationAlreadyProcessed) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        except InvitationEmailMismatch as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
            ) from e

    # 5. Listar invitaciones pendientes dirigidas al correo del usuario
    @router.get(
        "/invitations/me",
        response_model=list[SupplierInvitation],
        summary="Listar invitaciones pendientes asociadas al correo del usuario",
    )
    async def list_my_invitations(
        current_user: Annotated[User, Depends(get_current_user)],
        invitation_repo: Annotated[
            ISupplierInvitationRepository, Depends(get_supplier_invitation_repo)
        ],
    ):
        return await invitation_repo.list_by_email(
            current_user.email, status=InvitationStatus.PENDING
        )

    return router
