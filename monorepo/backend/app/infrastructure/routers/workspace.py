import logging
from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)

from app.application.repositories.supplier_invitation_repository import (
    ISupplierInvitationRepository,
)
from app.application.repositories.supplier_member_repository import (
    ISupplierMemberRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.user_repository import IUserRepository
from app.application.schemas.workspace_schema import (
    AcceptInvitationSchema,
    CreateInvitationSchema,
    InvitationDetailsSchema,
    RejectInvitationSchema,
    SwitchWorkspaceSchema,
    UserPendingInvitationSchema,
    WorkspaceMemberDetailSchema,
    WorkspaceMemberSummarySchema,
)
from app.application.services.email_service import EmailMessage, IEmailService
from app.application.services.email_templates import (
    build_invitation_html_body,
    build_invitation_subject,
    build_invitation_text_body,
)
from app.application.use_cases.workspace.accept_supplier_invitation import (
    AcceptSupplierInvitationUseCase,
)
from app.application.use_cases.workspace.cancel_supplier_invitation import (
    CancelSupplierInvitationUseCase,
)
from app.application.use_cases.workspace.create_supplier_invitation import (
    CreateSupplierInvitationUseCase,
)
from app.application.use_cases.workspace.get_invitation_details import (
    GetInvitationDetailsUseCase,
)
from app.application.use_cases.workspace.reject_supplier_invitation import (
    RejectSupplierInvitationUseCase,
)
from app.application.use_cases.workspace.revoke_supplier_member import (
    RevokeSupplierMemberUseCase,
)
from app.application.use_cases.workspace.switch_workspace import (
    SwitchWorkspaceUseCase,
)
from app.config import settings
from app.domain.entities.supplier_invitation import (
    InvitationStatus,
    SupplierInvitation,
)
from app.domain.entities.supplier_member import (
    MemberRole,
    MemberStatus,
    UserWorkspaceSummary,
    WorkspaceContext,
)
from app.domain.entities.user import User
from app.domain.errors.membership_errors import (
    CannotRevokeOwnMembership,
    InvitationAlreadyPending,
    InvitationAlreadyProcessed,
    InvitationCancelledOrInvalid,
    InvitationEmailMismatch,
    InvitationExpired,
    InvitationNotFound,
    MembershipNotFound,
    UnauthorizedWorkspaceAction,
    UserAlreadyMember,
)
from app.domain.errors.supplier_errors import SupplierNotFound

logger = logging.getLogger(__name__)


async def _send_invitation_email_safe(
    email_service: IEmailService,
    message: EmailMessage,
) -> None:
    try:
        await email_service.send(message)
    except Exception as exc:
        logger.warning(
            "No se pudo despachar el correo de invitación a %s: %s",
            message.to,
            exc,
        )


def create_workspace_router(
    get_current_user: Callable,
    get_current_workspace_context: Callable,
    get_supplier_member_repo: Callable,
    get_supplier_invitation_repo: Callable,
    get_supplier_repo: Callable,
    get_user_repo: Callable | None = None,
    get_email_service: Callable | None = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/workspaces",
        tags=["Workspaces & Invitations"],
    )

    user_repo_dep = get_user_repo or (lambda: None)
    email_service_dep = get_email_service or (lambda: None)

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

    # 2. Crear una invitación para unirse a un espacio de trabajo (CA2, CA3)
    @router.post(
        "/invitations",
        response_model=SupplierInvitation,
        status_code=status.HTTP_201_CREATED,
        summary="Enviar invitación a un usuario para unirse al espacio de trabajo",
    )
    async def create_invitation(
        data: CreateInvitationSchema,
        background_tasks: BackgroundTasks,
        current_user: Annotated[User, Depends(get_current_user)],
        invitation_repo: Annotated[
            ISupplierInvitationRepository, Depends(get_supplier_invitation_repo)
        ],
        member_repo: Annotated[
            ISupplierMemberRepository, Depends(get_supplier_member_repo)
        ],
        supplier_repo: Annotated[ISupplierRepository, Depends(get_supplier_repo)],
        user_repo: Annotated[IUserRepository | None, Depends(user_repo_dep)] = None,
        email_service: Annotated[
            IEmailService | None, Depends(email_service_dep)
        ] = None,
    ):
        try:
            invitation = await CreateSupplierInvitationUseCase(
                invitation_repo=invitation_repo,
                member_repo=member_repo,
                supplier_repo=supplier_repo,
                user_repo=user_repo,
            ).execute(data, inviter_user_id=current_user.id)
        except SupplierNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except UnauthorizedWorkspaceAction as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
            ) from e
        except (UserAlreadyMember, InvitationAlreadyPending) as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(e)
            ) from e

        if email_service is not None:
            supplier = await supplier_repo.get_by_id(data.supplier_id)
            supplier_name = (
                (supplier.trade_name or supplier.legal_name)
                if supplier
                else "Organización"
            )
            inviter_name = current_user.full_name or current_user.email
            message = EmailMessage(
                to=invitation.email,
                subject=build_invitation_subject(supplier_name),
                text_body=build_invitation_text_body(
                    supplier_name=supplier_name,
                    inviter_name=inviter_name,
                    role=invitation.role,
                    base_url=settings.app_base_url,
                    token=invitation.token,
                ),
                html_body=build_invitation_html_body(
                    supplier_name=supplier_name,
                    inviter_name=inviter_name,
                    role=invitation.role,
                    base_url=settings.app_base_url,
                    token=invitation.token,
                ),
            )
            background_tasks.add_task(
                _send_invitation_email_safe, email_service, message
            )

        return invitation

    # 3. Verificar token de invitación (público o autenticado) (CA8)
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
        except (
            InvitationExpired,
            InvitationCancelledOrInvalid,
            InvitationAlreadyProcessed,
        ) as e:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(e)) from e
        except SupplierNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e

    # 4. Aceptar invitación con la cuenta autenticada (CA6, CA8)
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
                last_access_at=member.last_access_at,
                created_at=member.created_at,
            )
        except InvitationNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except (
            InvitationExpired,
            InvitationAlreadyProcessed,
            InvitationCancelledOrInvalid,
        ) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        except InvitationEmailMismatch as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
            ) from e

    # 5. Rechazar invitación con la cuenta autenticada (CA4, CA8)
    @router.post(
        "/invitations/reject",
        response_model=SupplierInvitation,
        summary="Rechazar una invitación pendiente dirigida al usuario actual",
    )
    async def reject_invitation(
        data: RejectInvitationSchema,
        current_user: Annotated[User, Depends(get_current_user)],
        invitation_repo: Annotated[
            ISupplierInvitationRepository, Depends(get_supplier_invitation_repo)
        ],
    ):
        try:
            return await RejectSupplierInvitationUseCase(
                invitation_repo=invitation_repo,
            ).execute(token=data.token, current_user=current_user)
        except InvitationNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except (
            InvitationExpired,
            InvitationAlreadyProcessed,
            InvitationCancelledOrInvalid,
        ) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        except InvitationEmailMismatch as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
            ) from e

    # 6. Cancelar invitación pendiente por parte del administrador (CA7, CA8)
    @router.delete(
        "/invitations/{invitation_id}",
        response_model=SupplierInvitation,
        summary="Cancelar una invitación pendiente (solo administrador)",
    )
    async def cancel_invitation(
        invitation_id: UUID,
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
            return await CancelSupplierInvitationUseCase(
                invitation_repo=invitation_repo,
                member_repo=member_repo,
                supplier_repo=supplier_repo,
            ).execute(invitation_id=invitation_id, actor_user_id=current_user.id)
        except (InvitationNotFound, SupplierNotFound) as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except UnauthorizedWorkspaceAction as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
            ) from e
        except InvitationAlreadyProcessed as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e

    # 7. Listar invitaciones pendientes dirigidas al correo del usuario (CA4, CA5)
    @router.get(
        "/invitations/me",
        response_model=list[UserPendingInvitationSchema],
        summary="Listar invitaciones pendientes asociadas al correo del usuario",
    )
    async def list_my_invitations(
        current_user: Annotated[User, Depends(get_current_user)],
        invitation_repo: Annotated[
            ISupplierInvitationRepository, Depends(get_supplier_invitation_repo)
        ],
        supplier_repo: Annotated[ISupplierRepository, Depends(get_supplier_repo)],
        user_repo: Annotated[IUserRepository | None, Depends(user_repo_dep)] = None,
    ):
        raw_invitations = await invitation_repo.list_by_email(
            current_user.email, status=InvitationStatus.PENDING
        )
        enriched: list[UserPendingInvitationSchema] = []
        for inv in raw_invitations:
            if not inv.is_pending():
                continue
            supplier = await supplier_repo.get_by_id(inv.supplier_id)
            supplier_name = (
                (supplier.trade_name or supplier.legal_name)
                if supplier
                else "Organización"
            )
            supplier_rut = supplier.rut if supplier else ""
            invited_by_name: str | None = None
            if user_repo is not None:
                inviter = await user_repo.get_by_id(inv.invited_by_user_id)
                if inviter is not None:
                    invited_by_name = inviter.full_name or inviter.email
            enriched.append(
                UserPendingInvitationSchema(
                    id=inv.id,
                    supplier_id=inv.supplier_id,
                    supplier_name=supplier_name,
                    supplier_rut=supplier_rut,
                    invited_by_user_id=inv.invited_by_user_id,
                    invited_by_name=invited_by_name,
                    email=inv.email,
                    role=inv.role,
                    token=inv.token,
                    status=inv.status,
                    expires_at=inv.expires_at,
                    created_at=inv.created_at,
                    accepted_at=inv.accepted_at,
                )
            )
        return enriched

    # 8. Listar miembros actuales de una empresa (CA1)
    @router.get(
        "/{supplier_id}/members",
        response_model=list[WorkspaceMemberDetailSchema],
        summary="Listar miembros activos de una empresa",
    )
    async def list_workspace_members(
        supplier_id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        member_repo: Annotated[
            ISupplierMemberRepository, Depends(get_supplier_member_repo)
        ],
        supplier_repo: Annotated[ISupplierRepository, Depends(get_supplier_repo)],
        user_repo: Annotated[IUserRepository | None, Depends(user_repo_dep)] = None,
    ):
        supplier = await supplier_repo.get_by_id(supplier_id)
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El espacio de trabajo solicitado no existe.",
            )

        caller_member = await member_repo.get_by_user_and_supplier(
            current_user.id, supplier_id
        )
        is_member = (
            caller_member is not None and caller_member.status == MemberStatus.ACTIVE
        ) or (supplier.user_id == current_user.id)
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para ver los miembros de esta empresa.",
            )

        members = await member_repo.list_by_supplier_id(
            supplier_id, status=MemberStatus.ACTIVE
        )
        details: list[WorkspaceMemberDetailSchema] = []
        seen_user_ids: set[UUID] = set()

        for m in members:
            seen_user_ids.add(m.user_id)
            user_obj = (
                await user_repo.get_by_id(m.user_id) if user_repo is not None else None
            )
            full_name = (
                (user_obj.full_name or user_obj.email) if user_obj else "Usuario"
            )
            email = user_obj.email if user_obj else ""
            details.append(
                WorkspaceMemberDetailSchema(
                    id=m.id,
                    user_id=m.user_id,
                    supplier_id=m.supplier_id,
                    full_name=full_name,
                    email=email,
                    role=m.role,
                    status=m.status,
                    last_access_at=m.last_access_at or m.updated_at or m.created_at,
                    created_at=m.created_at,
                )
            )

        if supplier.user_id and supplier.user_id not in seen_user_ids:
            owner_obj = (
                await user_repo.get_by_id(supplier.user_id)
                if user_repo is not None
                else None
            )
            details.insert(
                0,
                WorkspaceMemberDetailSchema(
                    id=supplier.id,
                    user_id=supplier.user_id,
                    supplier_id=supplier.id,
                    full_name=(owner_obj.full_name or owner_obj.email)
                    if owner_obj
                    else "Administrador",
                    email=owner_obj.email if owner_obj else "",
                    role=MemberRole.ADMIN,
                    status=MemberStatus.ACTIVE,
                    last_access_at=supplier.updated_at or supplier.created_at,
                    created_at=supplier.created_at,
                ),
            )

        return details

    # 8b. Revocar acceso de un miembro del equipo (solo Admin) (HU-13: CA2, CA4, CA5)
    @router.delete(
        "/{supplier_id}/members/{member_id}",
        response_model=WorkspaceMemberSummarySchema,
        summary="Revocar el acceso de un miembro del equipo (solo administrador)",
        responses={
            400: {"description": "Un administrador no puede revocar su propio acceso"},
            403: {"description": "Solo los administradores pueden revocar miembros"},
            404: {"description": "Espacio de trabajo o miembro no encontrado"},
        },
    )
    async def revoke_workspace_member(
        supplier_id: UUID,
        member_id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        member_repo: Annotated[
            ISupplierMemberRepository, Depends(get_supplier_member_repo)
        ],
        supplier_repo: Annotated[ISupplierRepository, Depends(get_supplier_repo)],
    ):
        """Inactiva la membresía de un representante en la empresa indicada.

        Solo los usuarios con rol administrador en la empresa pueden ejecutar
        esta acción, y se impide que un administrador revoque su propia cuenta.
        """
        try:
            revoked = await RevokeSupplierMemberUseCase(
                member_repo=member_repo,
                supplier_repo=supplier_repo,
            ).execute(
                supplier_id=supplier_id,
                member_id=member_id,
                actor_user_id=current_user.id,
            )
            return WorkspaceMemberSummarySchema(
                id=revoked.id,
                user_id=revoked.user_id,
                supplier_id=revoked.supplier_id,
                role=revoked.role,
                status=revoked.status,
                last_access_at=revoked.last_access_at,
                created_at=revoked.created_at,
            )
        except (SupplierNotFound, MembershipNotFound) as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except UnauthorizedWorkspaceAction as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
            ) from e
        except CannotRevokeOwnMembership as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e

    # 9. Listar invitaciones pendientes de una empresa (solo Admin) (CA1, CA2)
    @router.get(
        "/{supplier_id}/invitations",
        response_model=list[SupplierInvitation],
        summary="Listar invitaciones pendientes de una empresa (solo administrador)",
    )
    async def list_workspace_invitations(
        supplier_id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        invitation_repo: Annotated[
            ISupplierInvitationRepository, Depends(get_supplier_invitation_repo)
        ],
        member_repo: Annotated[
            ISupplierMemberRepository, Depends(get_supplier_member_repo)
        ],
        supplier_repo: Annotated[ISupplierRepository, Depends(get_supplier_repo)],
    ):
        supplier = await supplier_repo.get_by_id(supplier_id)
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El espacio de trabajo solicitado no existe.",
            )

        caller_member = await member_repo.get_by_user_and_supplier(
            current_user.id, supplier_id
        )
        is_admin = (caller_member is not None and caller_member.is_admin()) or (
            supplier.user_id == current_user.id
        )
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo los administradores pueden ver las invitaciones pendientes.",
            )

        invitations = await invitation_repo.list_by_supplier_id(supplier_id)
        return [
            inv
            for inv in invitations
            if inv.is_pending() or inv.status == InvitationStatus.REJECTED
        ]

    # 10. Conmutar espacio de trabajo activo (CA-3, CA-4)
    @router.post(
        "/switch",
        response_model=WorkspaceContext,
        summary="Conmutar espacio de trabajo activo y recalcular permisos dinámicos",
    )
    async def switch_workspace(
        data: SwitchWorkspaceSchema,
        response: Response,
        current_user: Annotated[User, Depends(get_current_user)],
        member_repo: Annotated[
            ISupplierMemberRepository, Depends(get_supplier_member_repo)
        ],
        supplier_repo: Annotated[ISupplierRepository, Depends(get_supplier_repo)],
    ):
        try:
            context = await SwitchWorkspaceUseCase(
                member_repo=member_repo,
                supplier_repo=supplier_repo,
            ).execute(current_user=current_user, data=data)

            # Establecer cookie active_workspace_id
            response.set_cookie(
                key="active_workspace_id",
                value=str(context.active_supplier_id),
                path="/",
                httponly=True,
                secure=bool(settings.auth_cookie_secure),
                samesite=settings.auth_cookie_samesite,
                max_age=settings.access_token_expire_minutes * 60,
            )
            return context
        except SupplierNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except UnauthorizedWorkspaceAction as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
            ) from e

    # 10b. Limpiar espacio de trabajo activo de la sesión (HU-13: CA3)
    @router.post(
        "/clear-active",
        status_code=status.HTTP_204_NO_CONTENT,
        response_model=None,
        summary="Limpiar la cookie de espacio de trabajo activo de la sesión",
    )
    async def clear_active_workspace(
        _current_user: Annotated[User, Depends(get_current_user)],
    ) -> Response:
        """Elimina la cookie `active_workspace_id` para restablecer el contexto al volver al inicio."""
        res = Response(status_code=status.HTTP_204_NO_CONTENT)
        res.delete_cookie(key="active_workspace_id", path="/")
        return res

    # 11. Obtener contexto activo actual
    @router.get(
        "/current",
        response_model=WorkspaceContext,
        summary="Obtener el contexto activo de espacio de trabajo y permisos del usuario",
    )
    async def get_current_workspace(
        response: Response,
        context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
    ):
        response.set_cookie(
            key="active_workspace_id",
            value=str(context.active_supplier_id),
            path="/",
            httponly=True,
            secure=bool(settings.auth_cookie_secure),
            samesite=settings.auth_cookie_samesite,
            max_age=settings.access_token_expire_minutes * 60,
        )
        return context

    return router
