from datetime import datetime, timezone
from uuid import UUID

from pydantic import ValidationError

from app.application.repositories.membership_repository import IMembershipRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.supplier_vector_repository import (
    ISupplierVectorRepository,
)
from app.application.schemas.supplier_schema import CreateSupplierSchema
from app.domain.entities.membership import (
    MembershipRole,
    MembershipStatus,
    SupplierMembership,
)
from app.domain.entities.supplier import Supplier
from app.domain.errors.membership_errors import AlreadyHasSupplier
from app.domain.errors.supplier_errors import (
    SupplierAlreadyExists,
    SupplierValidationError,
)


class CreateSupplierUseCase:
    def __init__(
        self,
        repo: ISupplierRepository,
        vector_repo: ISupplierVectorRepository,
        membership_repo: IMembershipRepository,
    ):
        self.repo = repo
        self.vector_repo = vector_repo
        self.membership_repo = membership_repo

    async def execute(
        self, data: CreateSupplierSchema, user_id: UUID
    ) -> tuple[Supplier, SupplierMembership]:
        # El creador no puede pertenecer ya a otra empresa (regla: una por usuario)
        if await self.membership_repo.get_by_user(user_id) is not None:
            raise AlreadyHasSupplier()

        # Primero valida el formato — si es inválido no tocas la BD
        try:
            supplier = Supplier(**data.model_dump())
        except ValidationError as e:
            raise SupplierValidationError(str(e.errors()[0]["msg"]))

        # Luego consulta la BD solo si el RUT es válido
        existing = await self.repo.get_by_rut(data.rut)
        if existing:
            raise SupplierAlreadyExists(data.rut)

        # Guarda el proveedor en PostgreSQL
        saved_supplier = await self.repo.save(supplier)

        # TODO: generar embedding con EmbeddingService e indexar en Qdrant
        # Embedding hardcodeado para pruebas — reemplazar con EmbeddingService
        embedding = [0.1] * 1024
        self.vector_repo.upsert(saved_supplier.id, embedding)

        # El creador queda como admin activo de la empresa recién creada
        membership = SupplierMembership(
            user_id=user_id,
            supplier_id=saved_supplier.id,
            role=MembershipRole.ADMIN,
            status=MembershipStatus.ACTIVE,
            joined_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        saved_membership = await self.membership_repo.save(membership)

        return saved_supplier, saved_membership
