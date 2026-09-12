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
from app.domain.entities.supplier import Supplier
from app.domain.entities.supplier_member import (
    MemberRole,
    MemberStatus,
    SupplierMember,
)
from app.domain.errors.supplier_errors import (
    SupplierAlreadyExists,
    SupplierValidationError,
)


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
        member_repo: ISupplierMemberRepository | None = None,
    ):
        self.repo = repo
        self.vector_repo = vector_repo
        self.embedding_service = embedding_service
        self.member_repo = member_repo

    async def execute(
        self, data: CreateSupplierSchema, user_id: UUID | None = None
    ) -> Supplier:
        try:
            supplier = Supplier(**data.model_dump(), user_id=user_id)
        except ValidationError as e:
            raise SupplierValidationError(str(e.errors()[0]["msg"])) from e

        existing = await self.repo.get_by_rut(data.rut)
        if existing:
            raise SupplierAlreadyExists(data.rut)

        text = _build_supplier_text(data)
        vectors = await self.embedding_service.embed([text])

        saved_supplier = await self.repo.save(supplier)
        self.vector_repo.upsert(saved_supplier.id, vectors[0])

        if user_id is not None and self.member_repo is not None:
            await self.member_repo.save(
                SupplierMember(
                    user_id=user_id,
                    supplier_id=saved_supplier.id,
                    role=MemberRole.ADMIN,
                    status=MemberStatus.ACTIVE,
                )
            )

        return saved_supplier
