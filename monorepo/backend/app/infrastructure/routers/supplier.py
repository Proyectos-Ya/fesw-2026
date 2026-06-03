from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.repositories.membership_repository import IMembershipRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.supplier_vector_repository import (
    ISupplierVectorRepository,
)
from app.application.schemas.membership_schema import (
    MembershipPublicSchema,
    SupplierCreatedSchema,
)
from app.application.schemas.supplier_schema import CreateSupplierSchema
from app.application.use_cases.supplier.create_supplier import CreateSupplierUseCase
from app.application.use_cases.supplier.get_supplier import GetSupplierUseCase
from app.domain.entities.supplier import Supplier
from app.domain.entities.user import User
from app.domain.errors.membership_errors import AlreadyHasSupplier
from app.domain.errors.supplier_errors import (
    SupplierAlreadyExists,
    SupplierNotFound,
    SupplierValidationError,
)


def create_supplier_router(
    get_supplier_repo: Callable,
    get_supplier_vector_repo: Callable,
    get_membership_repo: Callable,
    get_current_user: Callable,
) -> APIRouter:
    """
    Fábrica del router de proveedores. Todas las rutas requieren sesión iniciada.
    Recibe las funciones de dependencia, nunca las implementaciones concretas.
    """
    router = APIRouter(
        prefix="/suppliers",
        tags=["Suppliers"],
        dependencies=[Depends(get_current_user)],
    )

    @router.post(
        "/",
        response_model=SupplierCreatedSchema,
        status_code=status.HTTP_201_CREATED,
        responses={
            400: {"description": "Bad Request - Invalid supplier data"},
            409: {
                "description": "Conflict - Supplier exists or user already in a supplier"
            },
        },
    )
    async def create_supplier(
        data: CreateSupplierSchema,
        current_user: User = Depends(get_current_user),
        repo: ISupplierRepository = Depends(get_supplier_repo),
        vector_repo: ISupplierVectorRepository = Depends(get_supplier_vector_repo),
        membership_repo: IMembershipRepository = Depends(get_membership_repo),
    ):
        # Crea la empresa y deja al usuario autenticado como admin de ésta
        try:
            supplier, membership = await CreateSupplierUseCase(
                repo, vector_repo, membership_repo
            ).execute(data, current_user.id)
            return SupplierCreatedSchema(
                supplier=supplier,
                membership=MembershipPublicSchema(**membership.model_dump()),
            )
        except SupplierAlreadyExists as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        except AlreadyHasSupplier as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        except SupplierValidationError as e:
            # Regla de negocio inválida (ej: RUT mal formateado por lógica interna)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    @router.get(
        "/{supplier_id}",
        response_model=Supplier,
        responses={404: {"description": "Not Found - Supplier does not exist"}},
    )
    async def get_supplier(
        supplier_id: UUID,
        repo: ISupplierRepository = Depends(get_supplier_repo),
    ):
        # Busca un proveedor por su id interno
        try:
            return await GetSupplierUseCase(repo).execute(supplier_id)
        except SupplierNotFound as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return router
