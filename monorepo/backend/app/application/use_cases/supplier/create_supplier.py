import asyncio
import logging
from dataclasses import dataclass
from uuid import UUID

from pydantic import ValidationError

from app.application.repositories.supplier_member_repository import (
    ISupplierMemberRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.supplier_vector_repository import (
    ISupplierVectorRepository,
)
from app.application.schemas.supplier_schema import CreateSupplierSchema
from app.application.services.embedding_service import IEmbeddingService
from app.domain.entities.supplier import Supplier, format_rut
from app.domain.entities.supplier_member import (
    MemberRole,
    MemberStatus,
    SupplierMember,
)
from app.domain.errors.supplier_errors import (
    SupplierAlreadyExists,
    SupplierProfileIndexingUnavailable,
    SupplierValidationError,
)

logger = logging.getLogger(__name__)

# Tope por defecto para el embedding. Tiene que quedar por debajo del corte del
# cliente (60 s): si no, el backend sigue trabajando cuando el usuario ya vio el
# error, y termina creando la empresa a sus espaldas.
DEFAULT_EMBEDDING_DEADLINE_SECONDS = 45.0


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


@dataclass(frozen=True)
class CreateSupplierResult:
    supplier: Supplier
    # False cuando el usuario ya tenía esta misma empresa: fue un reintento.
    created: bool


class CreateSupplierUseCase:
    def __init__(
        self,
        repo: ISupplierRepository,
        vector_repo: ISupplierVectorRepository,
        embedding_service: IEmbeddingService,
        member_repo: ISupplierMemberRepository | None = None,
        embedding_deadline_seconds: float = DEFAULT_EMBEDDING_DEADLINE_SECONDS,
    ):
        self.repo = repo
        self.vector_repo = vector_repo
        self.embedding_service = embedding_service
        self.member_repo = member_repo
        self.embedding_deadline_seconds = embedding_deadline_seconds

    async def execute(
        self, data: CreateSupplierSchema, user_id: UUID | None = None
    ) -> Supplier:
        """Atajo para quien solo necesita la empresa, no si ya existía."""
        return (await self.create(data, user_id=user_id)).supplier

    async def create(
        self, data: CreateSupplierSchema, user_id: UUID | None = None
    ) -> CreateSupplierResult:
        try:
            supplier = Supplier(**data.model_dump(), user_id=user_id)
        except ValidationError as e:
            raise SupplierValidationError(str(e.errors()[0]["msg"])) from e

        # Verificación temprana: si el RUT ya existe, si pertenece al mismo usuario es un reintento.
        # Si pertenece a otro o no tiene dueño, es un conflicto.
        existing = await self.repo.get_by_rut(supplier.rut)
        if existing is not None:
            if user_id is not None and existing.user_id == user_id:
                return CreateSupplierResult(existing, created=False)
            raise SupplierAlreadyExists(supplier.rut)

        # El embedding se calcula ANTES de persistir. Es una llamada de red a un
        # proveedor externo y es, de lejos, el paso que más falla. Con el orden
        # inverso un timeout dejaba la empresa commiteada en Postgres pero sin
        # vector en Qdrant: aparecía en "Mi empresa" y al mismo tiempo matches y
        # el escaneo de alertas respondían que no existía, sin forma de arreglarlo
        # reintentando, porque el RUT ya estaba tomado.
        text = _build_supplier_text(data)
        vectors = await self._embed_within_deadline(text)

        # Entre las validaciones de arriba y este INSERT pasan los segundos del
        # embedding: otra petición pudo haber creado la empresa. La base lo
        # detecta con sus índices únicos; si la que ganó es del mismo usuario y
        # con el mismo RUT, este envío también termina bien.
        try:
            saved_supplier = await self.repo.add(supplier)
            if user_id is not None and self.member_repo is not None:
                new_member = SupplierMember(
                    user_id=user_id,
                    supplier_id=saved_supplier.id,
                    role=MemberRole.ADMIN,
                    status=MemberStatus.ACTIVE,
                )
                if hasattr(self.member_repo, "add"):
                    await self.member_repo.add(new_member)
                else:
                    await self.member_repo.save(new_member)
        except SupplierAlreadyExists:
            existing = await self.repo.get_by_rut(supplier.rut)
            if existing is None and user_id is not None:
                existing = await self.repo.get_by_user_id(user_id)
            if (
                existing is not None
                and user_id is not None
                and existing.user_id == user_id
                and _same_rut(existing.rut, supplier.rut)
            ):
                return CreateSupplierResult(existing, created=False)
            raise

        # Postgres y Qdrant se escriben como una sola operación: la fila queda
        # pendiente, se indexa el vector y recién entonces se confirma. Con el
        # commit antes del upsert, una caída de Qdrant dejaba la empresa sin
        # vector: visible en "Mi empresa" e inexistente para matches y alertas.
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

        return CreateSupplierResult(saved_supplier, created=True)

    async def _embed_within_deadline(self, text: str) -> list[list[float]]:
        """Calcula el embedding o corta en el tope, sin haber guardado nada.

        Cualquier fallo del proveedor —tope vencido, red, 5xx tras sus propios
        reintentos— significa lo mismo para quien crea la empresa: ahora no se
        pudo, y reintentar es seguro porque todavía no se escribió nada.
        """
        try:
            async with asyncio.timeout(self.embedding_deadline_seconds):
                return await self.embedding_service.embed([text])
        except Exception as exc:
            logger.warning("No se pudo calcular el embedding del proveedor: %r", exc)
            raise SupplierProfileIndexingUnavailable() from exc


def _same_rut(stored: str, candidate: str) -> bool:
    # Las filas anteriores a la normalización pueden estar sin puntos: se
    # comparan en formato canónico para no confundir un reintento con otra empresa.
    return format_rut(stored) == format_rut(candidate)


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
