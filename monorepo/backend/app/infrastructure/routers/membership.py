from typing import Callable, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.application.repositories.membership_repository import IMembershipRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.schemas.membership_schema import (
    JoinSupplierSchema,
    MembershipPublicSchema,
)
from app.application.use_cases.membership.approve_join import ApproveJoinUseCase
from app.application.use_cases.membership.list_memberships import ListMembershipsUseCase
from app.application.use_cases.membership.reject_join import RejectJoinUseCase
from app.application.use_cases.membership.request_join import RequestJoinUseCase
from app.domain.entities.membership import MembershipStatus
from app.domain.entities.user import User
from app.domain.errors.membership_errors import (
    AlreadyHasSupplier,
    MembershipNotFound,
    NotAuthorized,
)
from app.domain.errors.supplier_errors import SupplierNotFound


def create_membership_router(
    get_supplier_repo: Callable,
    get_membership_repo: Callable,
    get_current_user: Callable,
) -> APIRouter:
    """Fábrica del router de membresías de proveedores. Requiere sesión."""
    router = APIRouter(
        prefix="/suppliers",
        tags=["Suppliers"],
        dependencies=[Depends(get_current_user)],
    )

    @router.post(
        "/join",
        response_model=MembershipPublicSchema,
        status_code=status.HTTP_201_CREATED,
        responses={
            404: {"description": "No existe proveedor con ese RUT"},
            409: {"description": "El usuario ya pertenece a un proveedor"},
        },
    )
    async def request_join(
        data: JoinSupplierSchema,
        current_user: User = Depends(get_current_user),
        supplier_repo: ISupplierRepository = Depends(get_supplier_repo),
        membership_repo: IMembershipRepository = Depends(get_membership_repo),
    ):
        # El proveedor al que se quiere unir se identifica por su RUT (en el body)
        try:
            return await RequestJoinUseCase(supplier_repo, membership_repo).execute(
                data.rut, current_user.id
            )
        except AlreadyHasSupplier as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        except SupplierNotFound as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    @router.get(
        "/{supplier_id}/members",
        response_model=list[MembershipPublicSchema],
        responses={403: {"description": "Requiere ser admin del proveedor"}},
    )
    async def list_members(
        supplier_id: UUID,
        status_filter: Optional[MembershipStatus] = Query(default=None, alias="status"),
        current_user: User = Depends(get_current_user),
        membership_repo: IMembershipRepository = Depends(get_membership_repo),
    ):
        # ?status=active|pending para filtrar; sin filtro devuelve todos
        try:
            return await ListMembershipsUseCase(membership_repo).execute(
                supplier_id, current_user.id, status_filter
            )
        except NotAuthorized as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    @router.post(
        "/{supplier_id}/members/{membership_id}/approve",
        response_model=MembershipPublicSchema,
        responses={
            403: {"description": "Requiere ser admin del proveedor"},
            404: {"description": "Solicitud no encontrada"},
        },
    )
    async def approve_request(
        supplier_id: UUID,
        membership_id: UUID,
        current_user: User = Depends(get_current_user),
        membership_repo: IMembershipRepository = Depends(get_membership_repo),
    ):
        try:
            return await ApproveJoinUseCase(membership_repo).execute(
                supplier_id, membership_id, current_user.id
            )
        except NotAuthorized as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except MembershipNotFound as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    @router.post(
        "/{supplier_id}/members/{membership_id}/reject",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={
            403: {"description": "Requiere ser admin del proveedor"},
            404: {"description": "Solicitud no encontrada"},
        },
    )
    async def reject_request(
        supplier_id: UUID,
        membership_id: UUID,
        current_user: User = Depends(get_current_user),
        membership_repo: IMembershipRepository = Depends(get_membership_repo),
    ):
        try:
            await RejectJoinUseCase(membership_repo).execute(
                supplier_id, membership_id, current_user.id
            )
            return None
        except NotAuthorized as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except MembershipNotFound as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return router
