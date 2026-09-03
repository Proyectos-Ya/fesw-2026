from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.supplier_vector_repository import (
    ISupplierVectorRepository,
)
from app.application.schemas.supplier_schema import (
    CreateSupplierSchema,
    RutExistsResponse,
    UpdateSupplierSchema,
)
from app.application.services.embedding_service import IEmbeddingService
from app.application.use_cases.supplier.check_rut_exists import CheckRutExistsUseCase
from app.application.use_cases.supplier.create_supplier import CreateSupplierUseCase
from app.application.use_cases.supplier.get_supplier import GetSupplierUseCase
from app.application.use_cases.supplier.get_supplier_by_user import (
    GetSupplierByUserUseCase,
)
from app.application.use_cases.supplier.update_supplier import UpdateSupplierUseCase
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

    # Ruta sin barra final a proposito: declarada como "/" su forma canonica era
    # `/suppliers/`, y FastAPI respondia a `/suppliers` con un 307 cuya `Location`
    # es absoluta —host y esquema los toma de la peticion que ve el backend—. Tras
    # el proxy de Railway eso es `http://` y el dominio del backend, asi que el
    # navegador bloqueaba el salto por contenido mixto. Next ademas quita la barra
    # final antes de aplicar el rewrite, de modo que al backend siempre le llega
    # `/suppliers`: esa es la forma que tiene que existir.
    @router.post(
        "",
        response_model=Supplier,
        status_code=status.HTTP_201_CREATED,
        responses={
            400: {"description": "Bad Request - Invalid supplier data"},
            409: {"description": "Conflict - Supplier already exists"},
        },
    )
    async def create_supplier(
        data: CreateSupplierSchema,
        current_user: Annotated[User, Depends(get_current_user)],
        repo: Annotated[ISupplierRepository, Depends(get_supplier_repo)],
        vector_repo: Annotated[
            ISupplierVectorRepository, Depends(get_supplier_vector_repo)
        ],
        embedding_service: Annotated[IEmbeddingService, Depends(get_embedding_service)],
    ):
        # TEMPORAL solo para demo del CA de timeout (>1 min sin respuesta).
        # Descomentar para el primer intento: duerme 70s (el cliente aborta a los
        # 60s y muestra el error) y luego corta con 503 SIN persistir nada, por lo
        # que la empresa nunca se crea. Volver a comentar para el segundo intento.
        # import asyncio; await asyncio.sleep(100); raise HTTPException(status_code=503, detail="Simulación de demora del servidor")

        # Crea la empresa asociada al usuario autenticado:
        # la persiste en PostgreSQL e indexa su vector en Qdrant
        try:
            return await CreateSupplierUseCase(
                repo, vector_repo, embedding_service
            ).execute(data, user_id=current_user.id)
        except (SupplierAlreadyExists, UserAlreadyHasSupplier) as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(e)
            ) from e
        except SupplierValidationError as e:
            # Regla de negocio inválida (ej: RUT mal formateado por lógica interna)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e

    @router.get(
        "/me",
        response_model=Supplier,
        responses={404: {"description": "El usuario no tiene una empresa asociada"}},
    )
    async def get_my_supplier(
        current_user: Annotated[User, Depends(get_current_user)],
        repo: Annotated[ISupplierRepository, Depends(get_supplier_repo)],
    ):
        # Devuelve la empresa del usuario autenticado (o 404 si aún no crea una)
        try:
            return await GetSupplierByUserUseCase(repo).execute(current_user.id)
        except SupplierNotFoundForUser as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e

    @router.patch(
        "/me",
        response_model=Supplier,
        responses={
            400: {"description": "Datos de empresa inválidos"},
            404: {"description": "El usuario no tiene una empresa asociada"},
        },
    )
    async def update_my_supplier(
        data: UpdateSupplierSchema,
        current_user: Annotated[User, Depends(get_current_user)],
        repo: Annotated[ISupplierRepository, Depends(get_supplier_repo)],
        vector_repo: Annotated[
            ISupplierVectorRepository, Depends(get_supplier_vector_repo)
        ],
        embedding_service: Annotated[IEmbeddingService, Depends(get_embedding_service)],
    ):
        # Edita la empresa del usuario autenticado; re-indexa el vector si
        # cambian los campos que alimentan el matching
        try:
            return await UpdateSupplierUseCase(
                repo, vector_repo, embedding_service
            ).execute(current_user.id, data)
        except SupplierNotFoundForUser as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except SupplierValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e

    @router.get("/rut-exists", response_model=RutExistsResponse)
    async def rut_exists(
        rut: str,
        repo: Annotated[ISupplierRepository, Depends(get_supplier_repo)],
    ):
        # Verificación temprana de RUT duplicado para el wizard de creación.
        # Declarada antes de /{supplier_id} para que no se capture como id.
        return RutExistsResponse(exists=await CheckRutExistsUseCase(repo).execute(rut))

    @router.get(
        "/{supplier_id}",
        response_model=Supplier,
        responses={404: {"description": "Not Found - Supplier does not exist"}},
    )
    async def get_supplier(
        supplier_id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        repo: Annotated[ISupplierRepository, Depends(get_supplier_repo)],
    ):
        """Busca una empresa por su id interno, solo si es la del usuario.

        Sin la comprobación, cualquier usuario autenticado con un id de empresa
        ajeno obtenía su perfil completo **incluido el `user_id`**, que es
        justo lo que necesitaban las otras rutas que tomaban la identidad del
        cliente: un id filtrado se convertía en la llave de las demás.

        Devuelve 404 y no 403 a propósito: un 403 confirmaría que ese id existe.
        """
        try:
            supplier = await GetSupplierUseCase(repo).execute(supplier_id)
        except SupplierNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e

        if supplier.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No existe una empresa con ese identificador.",
            )
        return supplier

    return router
