from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.supplier_vector_repository import (
    ISupplierVectorRepository,
)
from app.application.schemas.supplier_schema import CreateSupplierSchema
from app.application.services.embedding_service import IEmbeddingService
from app.application.use_cases.supplier.create_supplier import CreateSupplierUseCase
from app.application.use_cases.supplier.get_supplier import GetSupplierUseCase
from app.application.use_cases.supplier.get_supplier_by_user import (
    GetSupplierByUserUseCase,
)
from app.domain.entities.supplier import Supplier
from app.domain.entities.user import User
from app.domain.errors.supplier_errors import (
    SupplierAlreadyExists,
    SupplierNotFound,
    SupplierNotFoundForUser,
    SupplierValidationError,
    UserAlreadyHasSupplier,
)


def create_supplier_router(
    get_supplier_repo: Callable,
    get_supplier_vector_repo: Callable,
    get_embedding_service: Callable,
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
        response_model=Supplier,
        status_code=status.HTTP_201_CREATED,
        responses={
            400: {"description": "Bad Request - Invalid supplier data"},
            409: {"description": "Conflict - Supplier already exists"},
        },
    )
    async def create_supplier(
        data: CreateSupplierSchema,
        current_user: User = Depends(get_current_user),
        repo: ISupplierRepository = Depends(get_supplier_repo),
        vector_repo: ISupplierVectorRepository = Depends(get_supplier_vector_repo),
        embedding_service: IEmbeddingService = Depends(get_embedding_service),
    ):
        # Crea la empresa asociada al usuario autenticado:
        # la persiste en PostgreSQL e indexa su vector en Qdrant
        try:
            return await CreateSupplierUseCase(repo, vector_repo, embedding_service).execute(
                data, user_id=current_user.id
            )
        except (SupplierAlreadyExists, UserAlreadyHasSupplier) as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        except SupplierValidationError as e:
            # Regla de negocio inválida (ej: RUT mal formateado por lógica interna)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    @router.get(
        "/me",
        response_model=Supplier,
        responses={404: {"description": "El usuario no tiene una empresa asociada"}},
    )
    async def get_my_supplier(
        current_user: User = Depends(get_current_user),
        repo: ISupplierRepository = Depends(get_supplier_repo),
    ):
        # Devuelve la empresa del usuario autenticado (o 404 si aún no crea una)
        try:
            return await GetSupplierByUserUseCase(repo).execute(current_user.id)
        except SupplierNotFoundForUser as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

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
