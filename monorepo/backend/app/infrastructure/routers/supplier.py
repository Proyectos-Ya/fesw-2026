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
from app.domain.entities.supplier import Supplier
from app.domain.errors.supplier_errors import (
    SupplierAlreadyExists,
    SupplierNotFound,
    SupplierValidationError,
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
    # TEMP: auth deshabilitada para conectar el formulario del proveedor desde el
    # front mientras no exista flujo de login. Re-proteger con
    # dependencies=[Depends(get_current_user)] cuando el login esté integrado.
    router = APIRouter(
        prefix="/suppliers",
        tags=["Suppliers"],
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
        repo: ISupplierRepository = Depends(get_supplier_repo),
        vector_repo: ISupplierVectorRepository = Depends(get_supplier_vector_repo),
        embedding_service: IEmbeddingService = Depends(get_embedding_service),
    ):
        # Crea la empresa: la persiste en PostgreSQL e indexa su vector en Qdrant
        try:
            return await CreateSupplierUseCase(repo, vector_repo, embedding_service).execute(data)
        except SupplierAlreadyExists as e:
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
