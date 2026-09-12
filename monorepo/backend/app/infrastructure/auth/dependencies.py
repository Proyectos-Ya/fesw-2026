from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.repositories.supplier_member_repository import (
    ISupplierMemberRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.user_repository import IUserRepository
from app.application.services.token_service import ITokenService
from app.domain.entities.supplier_member import (
    MemberRole,
    MemberStatus,
    WorkspaceContext,
)
from app.domain.entities.user import User
from app.domain.errors.auth_errors import InvalidToken

# auto_error=False: si no hay header Authorization no falla aquí; intentamos la cookie.
# Declarar el esquema hace que el botón "Authorize" de Swagger funcione.
_bearer_scheme = HTTPBearer(auto_error=False)


def build_get_current_user(
    get_user_repo: Callable,
    token_service: ITokenService,
    cookie_name: str,
) -> Callable:
    """Construye la dependencia get_current_user.

    Acepta el token desde el header 'Authorization: Bearer' (Swagger) o desde
    la cookie httpOnly (frontend). Devuelve la entidad User autenticada.
    """

    async def get_current_user(
        request: Request,
        user_repo: Annotated[IUserRepository, Depends(get_user_repo)],
        credentials: Annotated[
            HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
        ] = None,
    ) -> User:
        # 1) Header Authorization tiene prioridad; 2) si no, la cookie
        token = (
            credentials.credentials if credentials else request.cookies.get(cookie_name)
        )

        unauthorized = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )
        if not token:
            raise unauthorized

        try:
            user_id = token_service.decode_token(token)
        except InvalidToken:
            raise unauthorized from None

        user = await user_repo.get_by_id(user_id)
        if user is None or not user.active:
            raise unauthorized

        return user

    return get_current_user


def build_get_current_workspace_context(
    get_current_user: Callable,
    get_member_repo: Callable,
    get_supplier_repo: Callable,
    workspace_header: str = "X-Workspace-Id",
    workspace_cookie: str = "active_workspace_id",
) -> Callable:
    """Construye la dependencia para obtener el WorkspaceContext activo del usuario."""

    async def get_current_workspace_context(
        request: Request,
        current_user: Annotated[User, Depends(get_current_user)],
        member_repo: Annotated[ISupplierMemberRepository, Depends(get_member_repo)],
        supplier_repo: Annotated[ISupplierRepository, Depends(get_supplier_repo)],
    ) -> WorkspaceContext:
        # 1. Obtener workspace id desde header o cookie
        header_val = request.headers.get(workspace_header)
        cookie_val = request.cookies.get(workspace_cookie)
        target_id_raw = header_val or cookie_val

        target_supplier_id: UUID | None = None
        if target_id_raw:
            try:
                target_supplier_id = UUID(target_id_raw)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Identificador de espacio de trabajo inválido",
                )

        # 2. Si no se especificó un target_supplier_id, obtener la primera membresía activa
        if not target_supplier_id:
            memberships = await member_repo.list_by_user_id(
                current_user.id, status=MemberStatus.ACTIVE
            )
            if not memberships:
                # O si aún tiene el legacy supplier.user_id, obtenerlo
                legacy_supplier = await supplier_repo.get_by_user_id(current_user.id)
                if legacy_supplier:
                    target_supplier_id = legacy_supplier.id
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="El usuario no pertenece a ningún espacio de trabajo",
                    )
            else:
                target_supplier_id = memberships[0].supplier_id

        # 3. Validar membresía y existencia de empresa
        supplier = await supplier_repo.get_by_id(target_supplier_id)
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El espacio de trabajo solicitado no existe",
            )

        member = await member_repo.get_by_user_and_supplier(
            current_user.id, target_supplier_id
        )

        if not member:
            if supplier.user_id == current_user.id:
                # Compatibilidad legacy si user_id coincide
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
                return WorkspaceContext(
                    user_id=current_user.id,
                    active_supplier_id=supplier.id,
                    active_supplier_name=supplier.trade_name or supplier.legal_name,
                    role=MemberRole.ADMIN,
                    permissions=all_perms,
                    is_admin=True,
                )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes acceso a este espacio de trabajo",
            )

        if member.status != MemberStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tu membresía en este espacio de trabajo está inactiva o suspendida",
            )

        perms = [
            p
            for p in [
                "invite_members",
                "remove_members",
                "edit_company_profile",
                "manage_tenders",
                "view_matches",
                "save_tenders",
                "chat_assistant",
                "deep_analysis",
            ]
            if member.has_permission(p)
        ]

        return WorkspaceContext(
            user_id=current_user.id,
            active_supplier_id=supplier.id,
            active_supplier_name=supplier.trade_name or supplier.legal_name,
            role=member.role,
            permissions=perms,
            is_admin=member.is_admin(),
        )

    return get_current_workspace_context

