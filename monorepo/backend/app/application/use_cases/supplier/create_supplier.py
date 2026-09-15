import logging
from uuid import UUID

from pydantic import ValidationError

from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.supplier_vector_repository import (
    ISupplierVectorRepository,
)
from app.application.schemas.supplier_schema import CreateSupplierSchema
from app.application.services.embedding_service import IEmbeddingService
from app.domain.entities.supplier import Supplier
from app.domain.errors.supplier_errors import (
    SupplierAlreadyExists,
    SupplierValidationError,
    UserAlreadyHasSupplier,
)

logger = logging.getLogger(__name__)


def _build_supplier_text(data: CreateSupplierSchema | Supplier) -> str:
    parts = [data.legal_name]
    if data.trade_name:
        parts.append(data.trade_name)
    if data.description:
        parts.append(data.description)
    if data.sectors:
        parts.append(f"Sectores: {', '.join(data.sectors)}")
    if data.keywords:
        parts.append(f"Palabras clave: {', '.join(data.keywords)}")
    return ". ".join(parts)


class CreateSupplierUseCase:
    def __init__(
        self,
        repo: ISupplierRepository,
        vector_repo: ISupplierVectorRepository,
        embedding_service: IEmbeddingService,
    ):
        self.repo = repo
        self.vector_repo = vector_repo
        self.embedding_service = embedding_service

    async def execute(
        self, data: CreateSupplierSchema, user_id: UUID | None = None
    ) -> Supplier:
        try:
            supplier = Supplier(**data.model_dump(), user_id=user_id)
        except ValidationError as e:
            raise SupplierValidationError(str(e.errors()[0]["msg"])) from e

        # Se busca con el RUT ya normalizado por la entidad, no con el recibido
        existing = await self.repo.get_by_rut(supplier.rut)
        if existing:
            raise SupplierAlreadyExists(supplier.rut)

        # Regla de negocio: un usuario solo puede ser dueño de una empresa
        if user_id is not None and await self.repo.get_by_user_id(user_id):
            raise UserAlreadyHasSupplier(user_id)

        # El embedding se calcula ANTES de persistir. Es una llamada de red a un
        # proveedor externo y es, de lejos, el paso que más falla. Con el orden
        # inverso un timeout dejaba la empresa commiteada en Postgres pero sin
        # vector en Qdrant: aparecía en "Mi empresa" y al mismo tiempo matches y
        # el escaneo de alertas respondían que no existía, sin forma de arreglarlo
        # reintentando, porque el RUT ya estaba tomado.
        text = _build_supplier_text(data)
        vectors = await self.embedding_service.embed([text])

        # Postgres y Qdrant se escriben como una sola operación: la fila queda
        # pendiente, se indexa el vector y recién entonces se confirma. Con el
        # commit antes del upsert, una caída de Qdrant dejaba la empresa sin
        # vector: visible en "Mi empresa" e inexistente para matches y alertas.
        saved_supplier = await self.repo.add(supplier)
        try:
            await self.vector_repo.upsert(saved_supplier.id, vectors[0])
        except Exception:
            await self.repo.rollback()
            raise

        try:
            await self.repo.commit()
        except Exception:
            # Un vector sin fila no lo consulta nadie —el matching parte de SQL—,
            # pero se borra igual para no dejar basura en la colección.
            await _discard_vector(self.vector_repo, saved_supplier.id)
            await self.repo.rollback()
            raise

        return saved_supplier


async def _discard_vector(
    vector_repo: ISupplierVectorRepository, supplier_id: UUID
) -> None:
    # Compensación de mejor esfuerzo: si también falla, se registra y se deja
    # subir el error original, que es el que explica lo que pasó.
    try:
        await vector_repo.delete(supplier_id)
    except Exception:
        logger.exception(
            "No se pudo borrar el vector del proveedor %s tras un commit fallido.",
            supplier_id,
        )
