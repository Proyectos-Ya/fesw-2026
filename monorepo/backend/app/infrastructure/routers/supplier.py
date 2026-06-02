from typing import Callable
from fastapi import APIRouter, Depends, HTTPException, status

from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.use_cases.supplier.create_supplier import CreateSupplierUseCase
from app.application.use_cases.supplier.get_supplier import GetSupplierUseCase
from app.domain.entities.supplier import Supplier
from app.domain.errors.supplier_errors import SupplierAlreadyExists, SupplierNotFound, SupplierValidationError
from app.application.schemas.supplier_schema import CreateSupplierSchema
from app.application.repositories.supplier_vector_repository import SupplierVectorRepository


def create_supplier_router(get_supplier_repo: Callable, get_supplier_vector_repo: Callable) -> APIRouter:
    """
    Fábrica del router de proveedores.
    Recibe la función de dependencia del repo, nunca la implementación concreta.
    """
    router = APIRouter(prefix="/suppliers", tags=["Suppliers"])

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
        vector_repo: SupplierVectorRepository = Depends(get_supplier_vector_repo),
    ):
        # Delega la creación al caso de uso correspondiente
        try:
            return await CreateSupplierUseCase(repo, vector_repo).execute(data)
        except SupplierAlreadyExists as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        except SupplierValidationError as e:
            # Regla de negocio inválida (ej: RUT mal formateado por lógica interna)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
 

    @router.get(
            "/{rut}", response_model=Supplier,
            responses={
                404: {"description": "Not Found - Supplier does not exist"}
            },)
    async def get_supplier(
        rut: str,
        repo: ISupplierRepository = Depends(get_supplier_repo),
    ):
        # Busca un proveedor por RUT usando el caso de uso
        try:
            return await GetSupplierUseCase(repo).execute(rut)
        except SupplierNotFound as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return router