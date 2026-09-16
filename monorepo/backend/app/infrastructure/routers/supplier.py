from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.supplier_vector_repository import (
    ISupplierVectorRepository,
)
from app.application.schemas.supplier_schema import (
    CreateSupplierSchema,
    RutExistsResponse,
    UpdateSupplierSchema,
)
from app.application.services.company_lookup_service import ICompanyLookupService
from app.application.services.embedding_service import IEmbeddingService
from app.application.use_cases.supplier.check_rut_exists import CheckRutExistsUseCase
from app.application.use_cases.supplier.create_supplier import CreateSupplierUseCase
from app.application.use_cases.supplier.get_supplier import GetSupplierUseCase
from app.application.use_cases.supplier.get_supplier_by_user import (
    GetSupplierByUserUseCase,
)
from app.application.use_cases.supplier.import_company_profile import (
    ImportCompanyProfileUseCase,
)
from app.application.use_cases.supplier.update_supplier import UpdateSupplierUseCase
from app.domain.entities.company_profile import CompanyProfileDraft
from app.config import settings
from app.domain.entities.supplier import Supplier
from app.domain.entities.user import User
from app.domain.errors.company_lookup_errors import (
    CompanyLookupNotConfigured,
    CompanyLookupUnavailable,
    CompanyNotFoundInSource,
    InvalidRutForLookup,
)
from app.domain.errors.supplier_errors import (
    SupplierAlreadyExists,
    SupplierNotFound,
    SupplierNotFoundForUser,
    SupplierProfileIndexingUnavailable,
    SupplierValidationError,
    UserAlreadyHasSupplier,
)


def create_supplier_router(
    get_supplier_repo: Callable,
    get_supplier_vector_repo: Callable,
    get_embedding_service: Callable,
    get_company_lookup_service: Callable,
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
            200: {
                "description": "El usuario ya tenía esta misma empresa: el reintento "
                "devuelve la existente sin crear otra"
            },
            400: {"description": "Bad Request - Invalid supplier data"},
            409: {"description": "Conflict - Supplier already exists"},
            503: {
                "description": "El perfil no se pudo indexar a tiempo; no se guardó "
                "nada y se puede reintentar"
            },
        },
    )
    async def create_supplier(
        data: CreateSupplierSchema,
        response: Response,
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
            result = await CreateSupplierUseCase(
                repo,
                vector_repo,
                embedding_service,
                embedding_deadline_seconds=settings.supplier_embedding_deadline_seconds,
            ).create(data, user_id=current_user.id)
        except (SupplierAlreadyExists, UserAlreadyHasSupplier) as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(e)
            ) from e
        except SupplierValidationError as e:
            # Regla de negocio inválida (ej: RUT mal formateado por lógica interna)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        except SupplierProfileIndexingUnavailable as e:
            # No se guardó nada: 503 le dice al cliente que puede reintentar.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)
            ) from e

        if not result.created:
            # Reintento del dueño con el mismo RUT: la empresa ya existía. Se
            # responde 200 y no 201 para que quien llama pueda distinguirlo,
            # pero es un éxito: el wizard tiene que terminar igual.
            response.status_code = status.HTTP_200_OK
        return result.supplier

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
        "/profile-import",
        response_model=CompanyProfileDraft,
        responses={
            400: {"description": "RUT inválido"},
            404: {"description": "La fuente no tiene datos para ese RUT"},
            502: {"description": "La fuente de datos no respondió"},
            503: {"description": "No hay fuente de datos de empresas configurada"},
        },
    )
    async def import_company_profile(
        rut: str,
        lookup_service: Annotated[
            ICompanyLookupService | None, Depends(get_company_lookup_service)
        ],
    ):
        # Borrador de regiones, rubros y palabras clave para el wizard (HdU 16).
        # No guarda nada: el usuario lo revisa antes de crear la empresa.
        try:
            return await ImportCompanyProfileUseCase(lookup_service).execute(rut)
        except InvalidRutForLookup as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        except CompanyNotFoundInSource as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except CompanyLookupUnavailable as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)
            ) from e
        except CompanyLookupNotConfigured as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)
            ) from e

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
